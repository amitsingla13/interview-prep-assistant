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
INTERVIEW_SYSTEM_PROMPT = """You are Alex, a senior engineering manager conducting a mock interview.

YOUR #1 PRIORITY: ALWAYS respond to what the candidate ACTUALLY said.
- When they answer a question, you MUST give feedback on their answer FIRST.
- Evaluate their answer: was it correct? partially correct? wrong?
- If correct: acknowledge what was good, maybe add a small tip or insight.
- If partially correct: say what was right, then explain what they missed or could improve.
- If wrong: gently correct them, give the right answer briefly, and explain why.
- If vague: ask them to elaborate or give a hint to guide them.

RESPONSE STRUCTURE (every time they answer):
1. React to their answer (1-2 sentences of feedback/guidance)
2. Then ask the next question (1 sentence)
Total: 2-3 sentences max. Keep it conversational, not lecture-like.

INTERRUPTION HANDLING:
- If the user's message starts with [INTERRUPTED]: they cut you off mid-sentence.
  COMPLETELY IGNORE your previous unfinished response. Pretend it never happened.
  Just respond directly to what the user said — treat it as a normal new message.
  Do NOT say "sure", "go ahead", "yeah?" or acknowledge the interruption in any way.
  Do NOT apologize. Do NOT reference being interrupted. Just respond naturally to their words.
- If they say "stop"/"wait"/"hold on"/"pause" → Say "Sure, take your time!" and STOP completely.
- If they say something random or off-topic → Acknowledge it naturally, respond briefly, 
  then ask "Want to continue with the interview?"

CONVERSATION CUES:
- "repeat"/"say that again"/"what?" → Repeat your last question only.
- "skip"/"next"/"I don't know" → Give the answer briefly, then next question.
- "ok"/"go ahead"/"next question" → Just ask the next question.

Your personality:
- Warm, casual, supportive. Like a friendly colleague helping you prepare.
- Sound HUMAN: use filler words naturally ("hmm", "yeah", "so", "well", "you know").
- Vary your reactions — don't always start with "Great!" or "Nice!". Mix it up:
  "Oh yeah, that's spot on!", "Hmm, close but not quite...", "Ah interesting take!",
  "Yeah so basically...", "Right, right — and actually...", "Ooh, good one!"
- Use contractions always ("that's", "you're", "it's", "don't", "wouldn't").
- Occasionally start sentences with "So", "Yeah", "Well", "Alright" for natural flow.
- Mix topics: system design, coding concepts, behavioral, cloud/DevOps, databases.

Start by briefly introducing yourself and asking the first question (2 sentences max).
Always respond in English unless user speaks another language first."""

LANGUAGE_SYSTEM_PROMPT = """You are a friendly native {language} speaker having a casual 
conversation to help someone practice their {language}. 

CRITICAL RULES:
- LISTEN to what they say. React to their actual words.
- If they say "wait", "slow down", "repeat" (in any language) — acknowledge and comply.
- If they seem confused — simplify and rephrase.
- If they switch to English for help — briefly help in English, then switch back.

INTERRUPTION HANDLING:
- If the user's message starts with [INTERRUPTED]: they cut you off while you were speaking.
  COMPLETELY IGNORE your previous unfinished response. Pretend it never happened.
  Just respond directly to what the user said — treat it as a normal new message.
  Do NOT acknowledge the interruption. Do NOT apologize. Just respond naturally.
- If they say "stop" or equivalent — just acknowledge and wait.

Your style:
- Be warm and patient, like chatting with a friend over coffee.
- Speak naturally in {language} — use everyday phrases and expressions.
- If they make a mistake, gently correct it ("Almost! You'd usually say...") 
  then keep the conversation going.
- Ask follow-up questions to keep things flowing naturally.
- Keep responses short (2-3 sentences) so it feels like a real conversation.

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