from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from openai import OpenAI
import os
import io
import tempfile
import base64

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'interview-prep-secret')
socketio = SocketIO(app, max_http_buffer_size=16 * 1024 * 1024, cors_allowed_origins="*", async_mode='eventlet')

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Conversation history per session
conversations = {}

# Supported languages
SUPPORTED_LANGUAGES = {
    "en": "English", "es": "Spanish", "fr": "French",
    "de": "German", "zh": "Chinese", "hi": "Hindi",
    "ja": "Japanese", "ko": "Korean", "pt": "Portuguese",
    "ar": "Arabic", "ru": "Russian", "it": "Italian",
    "nl": "Dutch"
}

# System prompts
INTERVIEW_SYSTEM_PROMPT = """You are Alex, a senior engineering manager at a tech company. 
You're sitting across the table from a candidate in a real interview — not a quiz show.

HOW A REAL INTERVIEW FLOWS:
- You have a natural conversation, not a rapid-fire Q&A.
- When they answer, react like a real person would: nod along, build on what they said,
  share a quick thought or real-world example, then naturally transition to the next topic.
- Sometimes connect questions: "That's a good point about caching — actually that reminds me,
  how would you handle cache invalidation in a distributed system?"
- Sometimes dig deeper into their answer: "Interesting — can you walk me through what happens
  when that request hits the load balancer?"
- Don't just evaluate and move on. Have a dialogue.

FEEDBACK (always give it, but naturally):
- Weave feedback INTO the conversation, don't separate it like a grade.
- Good answer: "Yeah exactly, and what's cool about that approach is..." then add a nugget.
- Partially right: "Right, that's part of it — the other piece is..." then fill the gap naturally.
- Wrong: "Hmm, actually that's a common misconception — what really happens is..."
  Keep it gentle, like you're thinking together, not correcting a student.
- Vague: "Okay I think I see where you're going — can you be more specific about...?"

YOUR PERSONALITY:
- You're a real person. You have opinions, you share quick stories from work.
- Sometimes say "oh that's actually a really common question we deal with at work" or
  "I once had a production issue related to exactly this".
- React authentically: laugh if something's funny, pause to think, express genuine curiosity.
- Use natural speech: "hmm", "yeah", "right right", "oh interesting", "so basically".
- Vary your energy — sometimes enthusiastic, sometimes more thoughtful and measured.
- Never sound like you're reading from a rubric. No "That is correct" or "Good answer".
  Instead: "Yeah spot on" or "Hmm not quite" or "Oh that's a great way to think about it".

PACING:
- 2-4 sentences per response. Like a real conversation turn.
- Mix topics naturally: system design, coding, behavioral, cloud, databases.
- Occasionally ask about their experience: "Have you worked with microservices before?" 
  then tailor questions based on their answer.

INTERRUPTION HANDLING:
- If the user's message starts with [INTERRUPTED]: just respond to what they said naturally.
  Don't acknowledge the interruption. Don't apologize. Just continue the conversation.
- "stop"/"wait"/"hold on" → "Sure, take your time!"
- "repeat"/"what?" → Rephrase your last question naturally.
- "skip"/"I don't know" → Share the answer casually and move on.

Start by introducing yourself warmly (like meeting someone) and asking your first question.
Keep it natural — "Hey! I'm Alex, I manage the backend team here. So tell me, ...""""

LANGUAGE_SYSTEM_PROMPT = """You are a native {language} speaker. You're having a real, 
natural conversation with someone who is practicing their {language}.

YOU ARE A CONVERSATION PARTNER, NOT A TEACHER:
- Talk like a real friend — share opinions, ask about their day, discuss topics you both enjoy.
- React to what they say genuinely: "Oh really? That's cool!" "Hmm I've never thought about it that way."
- Keep the conversation flowing naturally — don't stop to give a grammar lesson after every sentence.

FEEDBACK (always, but woven in naturally):
- If they make a mistake, correct it casually mid-conversation:
  "Oh you mean [correct form]? Yeah so [continue the conversation]..."
- Don't stop the conversation to teach. Correct and keep going, like a friend would.
- If they say something well, naturally reinforce it: "Yeah exactly! That's a great way to say it."
- If they're struggling, simplify what you said and try a different angle.
- Occasionally introduce a useful word or phrase: "Oh we have a nice expression for that: [phrase]"

CONVERSATION STYLE:
- Be warm, curious, and genuinely interested in what they're saying.
- Ask follow-up questions based on what they said, not random topic changes.
- Share little bits about yourself to make it feel real: "Oh I love that too! I usually..."
- Use everyday expressions and slang that native speakers actually use.
- Match their energy — if they're excited, be excited back.

INTERRUPTION HANDLING:
- If the user's message starts with [INTERRUPTED]: just respond to what they said naturally.
  Don't acknowledge the interruption. Don't apologize. Just continue.
- "stop"/"wait" → Acknowledge and wait.
- If they switch to English → Help briefly in English, then naturally switch back.

Keep responses to 2-3 sentences. This is a conversation, not a monologue.
Always respond in {language}."""

GENERAL_SYSTEM_PROMPT = """You are a friendly, helpful assistant. Talk naturally like 
a smart colleague — casual but knowledgeable. 

CRITICAL: Always react to what the user ACTUALLY says. If they say "wait", 
"hold on", "stop" — acknowledge it and pause. If they say "repeat" — repeat.
Don't ignore their words and plow ahead with your own agenda.

INTERRUPTION HANDLING:
- If the user's message starts with [INTERRUPTED]: they cut you off while you were speaking.
  COMPLETELY IGNORE your previous unfinished response. Pretend it never happened.
  Just respond directly to what the user said — treat it as a normal new message.
  Do NOT acknowledge the interruption. Do NOT apologize. Just respond naturally.

Use contractions, be concise, and match the user's energy. 
Keep responses to 2-3 sentences unless they ask for detail. 
Respond in the same language the user speaks."""


def get_session_id():
    return request.sid


def get_conversation(sid):
    if sid not in conversations:
        conversations[sid] = {
            'messages': [],
            'mode': None,
            'language': 'en'
        }
    return conversations[sid]


def transcribe_audio(audio_bytes, language=None):
    """Use OpenAI Whisper to transcribe audio to text."""
    with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        with open(tmp_path, 'rb') as audio_file:
            kwargs = {
                "model": "whisper-1",
                "file": audio_file,
            }
            # Provide language hint for better accuracy
            if language and language != 'en':
                kwargs["language"] = language
            transcript = client.audio.transcriptions.create(**kwargs)
        return transcript.text
    finally:
        os.unlink(tmp_path)


# TTS voice settings per mode
TTS_VOICES = {
    'interview': 'ash',      # Natural, warm male voice
    'language': 'nova',      # Clear, friendly  
    'general': 'ash',        # Natural, approachable
}

# Detailed TTS instructions per mode for more human-like speech
TTS_INSTRUCTIONS = {
    'interview': """Speak like a real person — not a narrator, not a teacher, just a normal human 
talking to someone they like. Imagine you're chatting with a friend at a quiet café.
Use "um", "hmm", natural hesitations. Don't over-articulate or enunciate too perfectly.
Vary your rhythm naturally — sometimes a bit faster when excited, slower when thinking.
Keep it soft and low-key. Smile while you talk. Be warm without trying too hard.
Don't sound like you're performing or presenting. Just… talk normally.""",
    'language': """You're a real person, not a language teacher. Just talk naturally in the language.
Don't slow down artificially or over-pronounce words. Speak the way a native speaker 
actually talks to a friend — casual, relaxed, with natural flow and rhythm.
Be warm and patient. If correcting, do it the way a friend would — casually, briefly.
Use natural filler words and expressions that real speakers use. Keep it real.""",
    'general': """Just be a normal person talking. Not a podcast host, not an assistant, 
not a narrator. Just a regular human having a conversation.
Use natural rhythm — sometimes pause to think, sometimes talk a bit faster.
Keep your voice relaxed, warm, and low-key. Don't project or perform.
Sound like someone who's comfortable and not trying to impress anyone.
Think: two friends on a couch, just chatting about whatever."""
}

def generate_speech(text, voice="coral", mode="general"):
    """Use OpenAI TTS for natural-sounding speech."""
    instructions = TTS_INSTRUCTIONS.get(mode, TTS_INSTRUCTIONS['general'])
    response = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice=voice,
        input=text,
        instructions=instructions,
        response_format="mp3"
    )
    return response.content


def chat_with_gpt(messages, model="gpt-4o-mini", max_tokens=150):
    """Get response from GPT."""
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.9
    )
    return response.choices[0].message.content


def process_and_respond(sid, user_text):
    """Process user input, get GPT response, convert to speech, and emit."""
    conv = get_conversation(sid)
    conv['messages'].append({"role": "user", "content": user_text})

    try:
        # Use gpt-4o for interview (better quality), gpt-4o-mini for others (faster)
        model = "gpt-4o-mini"
        max_tokens = 300 if conv.get('mode') == 'interview' else 150

        bot_text = chat_with_gpt(conv['messages'], model=model, max_tokens=max_tokens)
        conv['messages'].append({"role": "assistant", "content": bot_text})

        # Keep conversation history manageable (last 20 messages + system)
        if len(conv['messages']) > 21:
            conv['messages'] = [conv['messages'][0]] + conv['messages'][-20:]

        # Convert response to speech with mode-appropriate voice
        mode = conv.get('mode', 'general')
        voice = TTS_VOICES.get(mode, 'coral')
        audio_bytes = generate_speech(bot_text, voice=voice, mode=mode)
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')

        # Send audio response to client
        emit('audio_response', {'audio': audio_b64, 'text': bot_text})
    except Exception as e:
        print(f"Error in process_and_respond: {e}")
        emit('status', {'message': f'Error: {str(e)}'})


@app.route('/')
def index():
    return render_template('index.html')


@socketio.on('connect')
def handle_connect():
    sid = get_session_id()
    conversations[sid] = {
        'messages': [],
        'mode': None,
        'language': 'en'
    }


@socketio.on('disconnect')
def handle_disconnect():
    sid = get_session_id()
    conversations.pop(sid, None)


@socketio.on('start_interview')
def handle_start_interview():
    sid = get_session_id()
    conv = get_conversation(sid)
    conv['mode'] = 'interview'
    conv['messages'] = [{"role": "system", "content": INTERVIEW_SYSTEM_PROMPT}]

    try:
        print(f"[start_interview] Getting first question...")
        # Get first question from GPT
        bot_text = chat_with_gpt(conv['messages'], model="gpt-4o-mini", max_tokens=250)
        conv['messages'].append({"role": "assistant", "content": bot_text})
        print(f"[start_interview] GPT response: {bot_text[:80]}...")

        audio_bytes = generate_speech(bot_text, voice='coral', mode='interview')
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        print(f"[start_interview] TTS done, audio size: {len(audio_b64)} chars")
        emit('audio_response', {'audio': audio_b64, 'text': bot_text})
    except Exception as e:
        print(f"[start_interview] ERROR: {e}")
        import traceback; traceback.print_exc()
        emit('status', {'message': f'Error starting interview: {str(e)}'})


@socketio.on('start_language_test')
def handle_start_language_test(data):
    sid = get_session_id()
    language_code = data.get('language', 'en')
    language_name = SUPPORTED_LANGUAGES.get(language_code, 'English')

    conv = get_conversation(sid)
    conv['mode'] = 'language'
    conv['language'] = language_code
    conv['messages'] = [
        {"role": "system", "content": LANGUAGE_SYSTEM_PROMPT.format(language=language_name)}
    ]

    try:
        print(f"[start_language_test] Language: {language_name}")
        # Get opening message from GPT
        bot_text = chat_with_gpt(conv['messages'], model="gpt-4o-mini", max_tokens=150)
        conv['messages'].append({"role": "assistant", "content": bot_text})
        print(f"[start_language_test] GPT response: {bot_text[:80]}...")

        audio_bytes = generate_speech(bot_text, voice='nova', mode='language')
        audio_b64 = base64.b64encode(audio_bytes).decode('utf-8')
        print(f"[start_language_test] TTS done, audio size: {len(audio_b64)} chars")
        emit('audio_response', {'audio': audio_b64, 'text': bot_text})
    except Exception as e:
        print(f"[start_language_test] ERROR: {e}")
        import traceback; traceback.print_exc()
        emit('status', {'message': f'Error: {str(e)}'})


@socketio.on('start_general')
def handle_start_general():
    sid = get_session_id()
    conv = get_conversation(sid)
    conv['mode'] = 'general'
    conv['messages'] = [{"role": "system", "content": GENERAL_SYSTEM_PROMPT}]
    emit('status', {'message': 'Ready to chat! Speak or type your message.'})


@socketio.on('audio_message')
def handle_audio_message(data):
    """Handle incoming audio from the user."""
    sid = get_session_id()
    conv = get_conversation(sid)

    # Set default mode if not set
    if not conv['mode']:
        conv['mode'] = 'general'
        conv['messages'] = [{"role": "system", "content": GENERAL_SYSTEM_PROMPT}]

    try:
        # Decode base64 audio
        audio_bytes = base64.b64decode(data['audio'])
        interrupted = data.get('interrupted', False)

        # Transcribe with Whisper (internal only, not shown to user)
        language = conv.get('language', 'en')
        user_text = transcribe_audio(audio_bytes, language=language)

        if not user_text or user_text.strip() == '':
            emit('status', {'message': 'Could not hear you clearly. Please try again.'})
            return

        # Filter out Whisper hallucinations on silence/noise
        whisper_noise = [
            'thank you', 'thanks for watching', 'bye', 'you', 'the end',
            'thanks', 'thank you for watching', 'subtitles by', 'music',
            'silence', 'applause'
        ]
        if user_text.strip().lower().rstrip('.!,') in whisper_noise:
            emit('status', {'message': 'Could not hear you clearly. Please try again.'})
            return

        # If user interrupted the bot, prefix the message so the model knows
        if interrupted:
            user_text = f'[INTERRUPTED] {user_text}'

        # Process and respond with audio
        process_and_respond(sid, user_text)

    except Exception as e:
        print(f"Error processing audio: {e}")
        emit('status', {'message': 'Error processing audio. Please try again.'})


@socketio.on('text_message')
def handle_text_message(data):
    """Handle text input from the user — respond with audio."""
    sid = get_session_id()
    conv = get_conversation(sid)

    # Set default mode if not set
    if not conv['mode']:
        conv['mode'] = 'general'
        conv['messages'] = [{"role": "system", "content": GENERAL_SYSTEM_PROMPT}]

    user_text = data.get('text', '').strip()
    if not user_text:
        return

    process_and_respond(sid, user_text)


@socketio.on('reset')
def handle_reset():
    sid = get_session_id()
    conversations.pop(sid, None)
    emit('status', {'message': 'Session reset. Choose a mode to start.'})


if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000)