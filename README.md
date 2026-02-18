# Voice Interview Preparation Assistant

A **real-time, speech-to-speech AI conversational bot** built with Python that simulates realistic interview practice, language speaking tests, and free-form voice conversations. The app uses OpenAI's latest models to create a natural, human-like voice interaction — no typing required. Think of it as having a friendly colleague you can practice with anytime.

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture & How It Works](#architecture--how-it-works)
- [Tech Stack](#tech-stack)
- [LLM Models Used](#llm-models-used)
- [Feature Breakdown](#feature-breakdown)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Challenges & Solutions](#challenges--solutions)
- [How to Explain This Project](#how-to-explain-this-project)

---

## Overview

This application is a **voice-first AI assistant** where users can:
1. **Practice IT interviews** — get asked real technical questions, receive instant feedback on answers, and get guided when wrong
2. **Practice speaking in 13 languages** — have conversations with a patient native speaker who corrects mistakes naturally
3. **Free chat** — talk about anything with a smart, casual AI colleague

The entire interaction is **speech-to-speech**: you speak, the AI listens, processes, and responds with a natural human-like voice. There is no visible transcription — it feels like a real phone call or face-to-face conversation.

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Voice Activity Detection (VAD)** | Automatically detects when you stop talking and processes your response — no button clicking needed |
| **Real-time Voice Interruption** | You can interrupt the bot mid-sentence by speaking — it stops immediately and listens to you |
| **Speech-to-Speech Pipeline** | User voice → Whisper STT → GPT reasoning → TTS voice response (all invisible to user) |
| **Natural Human-like Voice** | Uses OpenAI's `gpt-4o-mini-tts` with custom voice instructions for warm, expressive, non-robotic speech |
| **3 Distinct Modes** | IT Interview, Language Speaking Test, Free Chat — each with its own personality, voice, and behavior |
| **13 Language Support** | English, Spanish, French, German, Chinese, Hindi, Japanese, Korean, Portuguese, Arabic, Russian, Italian, Dutch |
| **Auto-listen Loop** | After the bot finishes speaking, it automatically starts listening again — hands-free conversation flow |
| **Instant Feedback** | In interview mode, the bot evaluates your answers, tells you what's right/wrong, and explains the correct approach |
| **Conversation Memory** | Maintains context across the conversation (last 20 messages) for coherent multi-turn dialogue |
| **Audio Interruption Detection** | When you speak during bot playback, it tags the message as `[INTERRUPTED]` so the AI acknowledges the interruption naturally |
| **Text + Voice Input** | Supports both typing and voice input for flexibility |
| **Mode-specific TTS Voices** | Different OpenAI voices per mode (coral/nova/shimmer) with tailored speech instructions |

---

## Architecture & How It Works

```
┌─────────────────────────────────────────────────────────┐
│                    BROWSER (Frontend)                    │
│                                                         │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────┐ │
│  │ MediaRecorder│   │  Web Audio   │   │   Audio      │ │
│  │ (WebM/Opus) │   │  API (VAD)   │   │   Playback   │ │
│  └──────┬──────┘   └──────┬───────┘   └──────▲───────┘ │
│         │                 │                   │         │
│         │   Base64 audio  │  Silence detect   │  MP3    │
│         └────────┬────────┘                   │         │
│                  │                            │         │
│          ┌───────▼────────┐          ┌────────┴───────┐ │
│          │  Socket.IO     │          │  Socket.IO     │ │
│          │  (emit)        │          │  (listen)      │ │
│          └───────┬────────┘          └────────▲───────┘ │
└──────────────────┼────────────────────────────┼─────────┘
                   │  WebSocket (real-time)      │
┌──────────────────▼────────────────────────────┼─────────┐
│                 FLASK SERVER (Backend)                    │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │                 Socket.IO Handlers                   │ │
│  │  audio_message │ text_message │ start_* │ reset     │ │
│  └────────┬───────┴──────────────┴─────────────────────┘ │
│           │                                              │
│  ┌────────▼────────┐                                     │
│  │  1. WHISPER STT  │  Transcribe user audio to text    │
│  │  (whisper-1)     │  (internal only, never shown)     │
│  └────────┬─────────┘                                    │
│           │  user_text                                   │
│  ┌────────▼─────────┐                                    │
│  │  2. GPT CHAT     │  Generate contextual response     │
│  │  (gpt-4o-mini)   │  using conversation history +     │
│  │                   │  system prompt (per mode)         │
│  └────────┬──────────┘                                   │
│           │  bot_text                                    │
│  ┌────────▼──────────┐                                   │
│  │  3. TTS SPEECH    │  Convert text to natural voice   │
│  │ (gpt-4o-mini-tts) │  with mode-specific voice +     │
│  │                    │  expressive instructions        │
│  └────────┬───────────┘                                  │
│           │  MP3 audio bytes (base64)                    │
│           └──────────────────────────────────────────►   │
└──────────────────────────────────────────────────────────┘
```

### Data Flow (per user message):
1. **User speaks** → Browser's `MediaRecorder` captures audio as WebM/Opus
2. **VAD detects silence** (~1.5s) → automatically stops recording
3. **Audio sent** via Socket.IO as base64-encoded string
4. **Whisper** transcribes audio to text (server-side, never exposed to user)
5. **GPT-4o-mini** generates a response using conversation history + system prompt
6. **gpt-4o-mini-tts** converts response text to natural speech audio (MP3)
7. **Audio streamed back** via Socket.IO → browser auto-plays the response
8. **Mic auto-starts** again → continuous conversation loop

---

## Tech Stack

### Backend
| Technology | Purpose | Why Chosen |
|-----------|---------|------------|
| **Python 3.13** | Core language | Rich AI/ML ecosystem, OpenAI SDK support |
| **Flask** | Web framework | Lightweight, perfect for single-page app |
| **Flask-SocketIO** | WebSocket communication | Real-time bidirectional audio streaming, much faster than HTTP polling |
| **OpenAI Python SDK (v1.0+)** | API client | Modern async-compatible client for GPT, Whisper, and TTS |
| **python-dotenv** | Environment config | Secure API key management |
| **tempfile** | Temp file handling | Whisper API requires file input, so audio bytes are written to temp `.webm` files |

### Frontend
| Technology | Purpose | Why Chosen |
|-----------|---------|------------|
| **Vanilla JavaScript** | UI logic | No framework overhead, direct browser API access |
| **Socket.IO Client 4.7** | WebSocket client | Matches Flask-SocketIO for reliable real-time messaging |
| **Web Audio API** | Voice Activity Detection | `AudioContext` + `AnalyserNode` for real-time microphone volume monitoring |
| **MediaRecorder API** | Audio capture | Browser-native recording in WebM/Opus format |
| **HTML5 Audio** | Playback | Auto-plays bot responses, supports interruption via `.pause()` |
| **Font Awesome 6.5** | Icons | Clean UI icons for mic, send, modes |
| **CSS3 Gradients + Animations** | Modern UI | Gradient backgrounds, pulse animation on mic button during recording |

### Communication
| Layer | Protocol | Format |
|-------|----------|--------|
| Client ↔ Server | **WebSocket** (Socket.IO) | JSON events with base64 audio payloads |
| Server → OpenAI | **HTTPS REST** | OpenAI SDK handles serialization |
| Audio encoding | **WebM/Opus** (upload) → **MP3** (response) | Opus for efficient capture, MP3 for universal playback |

---

## LLM Models Used

### 1. `gpt-4o-mini` — Chat/Reasoning
- **Used for**: Generating interview questions, evaluating answers, providing feedback, conversation
- **Why not gpt-4o**: Project-level API restrictions; gpt-4o-mini offers great quality at lower cost and faster response times
- **Temperature**: 0.9 (higher for more natural, varied responses)
- **Max tokens**: 300 (interview), 150 (language/general) — keeps responses concise

### 2. `whisper-1` — Speech-to-Text
- **Used for**: Transcribing user's voice recordings to text (server-side only)
- **Input**: WebM/Opus audio files
- **Key design decision**: Transcription is **never shown to the user** — the app feels purely speech-to-speech
- **Multi-language**: Whisper auto-detects the language spoken

### 3. `gpt-4o-mini-tts` — Text-to-Speech
- **Used for**: Converting bot text responses to natural human-like voice
- **Key feature**: Supports `instructions` parameter for controlling voice expressiveness
- **Voices used**:
  - `coral` — Interview mode (warm, professional)
  - `nova` — Language mode (clear, friendly)
  - `shimmer` — Free chat mode (casual, approachable)
- **Custom TTS instructions per mode**: Each mode has detailed voice direction (e.g., "sound genuinely pleased when giving positive feedback", "laugh a little if something is funny")

---

## Feature Breakdown

### 1. IT Interview Practice Mode
| Aspect | Implementation |
|--------|---------------|
| **Persona** | "Alex" — senior engineering manager |
| **System prompt** | Detailed instructions for feedback-first responses, natural filler words, varied reactions |
| **Topics** | System design, coding concepts, behavioral, cloud/DevOps, databases |
| **Feedback loop** | Evaluates every answer → correct/partial/wrong → explains why → next question |
| **Voice** | `coral` with warm office-conversation TTS instructions |
| **Conversation cues** | Handles "wait", "skip", "repeat", "I don't know" naturally |

### 2. Language Speaking Test Mode
| Aspect | Implementation |
|--------|---------------|
| **13 languages** | EN, ES, FR, DE, ZH, HI, JA, KO, PT, AR, RU, IT, NL |
| **Persona** | Native speaker friend |
| **Error correction** | Gentle inline corrections ("Almost! You'd usually say...") |
| **Dynamic prompt** | System prompt template with `{language}` placeholder filled at runtime |
| **Voice** | `nova` with patient native-speaker TTS instructions |
| **Language detection** | Whisper auto-detects; GPT responds in the selected language |

### 3. Free Chat Mode
| Aspect | Implementation |
|--------|---------------|
| **Persona** | Smart casual colleague |
| **Behavior** | Matches user's energy, responds in user's language |
| **Voice** | `shimmer` with casual coffee-chat TTS instructions |
| **Use case** | General conversation practice, Q&A, brainstorming |

### 4. Voice Activity Detection (VAD)
| Aspect | Implementation |
|--------|---------------|
| **Technology** | Web Audio API — `AudioContext` + `AnalyserNode` |
| **Detection method** | RMS (Root Mean Square) volume analysis every 100ms |
| **Silence threshold** | RMS < 15 (on 0-128 scale) = silence |
| **Auto-stop trigger** | 1.5 seconds of continuous silence after speech detected |
| **Result** | Hands-free: click mic once, then just talk naturally |

### 5. Real-time Voice Interruption
| Aspect | Implementation |
|--------|---------------|
| **Mic during playback** | Mic starts listening in "passive mode" while bot audio plays |
| **Interruption detection** | VAD detects user voice → immediately stops bot audio (`Audio.pause()`) |
| **Backend handling** | Interrupted messages prefixed with `[INTERRUPTED]` tag |
| **AI response** | System prompts instruct model to acknowledge interruption ("Oh sorry, go ahead!") |

### 6. Conversation Memory Management
| Aspect | Implementation |
|--------|---------------|
| **Storage** | In-memory Python dictionary keyed by Socket.IO session ID |
| **History limit** | Last 20 messages + system prompt (trimmed to prevent token overflow) |
| **Session lifecycle** | Created on `connect`, destroyed on `disconnect` or `reset` |

---

## Project Structure

```
├── src/
│   ├── app.py                 # Flask backend — all server logic, API calls, Socket.IO handlers
│   └── templates/
│       └── index.html         # Frontend — UI, VAD, audio recording/playback, Socket.IO client
├── requirements.txt           # Python dependencies
├── README.md                  # This file
├── .venv/                     # Python virtual environment
└── .env                       # API key (OPENAI_API_KEY) — not committed
```

### `src/app.py` — Backend (~350 lines)
- **System Prompts**: 3 detailed prompts (interview, language, general) with personality, rules, and interruption handling
- **`transcribe_audio()`**: Saves WebM bytes to temp file → calls Whisper API → returns text
- **`generate_speech()`**: Calls gpt-4o-mini-tts with mode-specific voice + instructions → returns MP3 bytes
- **`chat_with_gpt()`**: Sends conversation history to gpt-4o-mini → returns response text
- **`process_and_respond()`**: Orchestrates the full STT → GPT → TTS pipeline
- **Socket.IO handlers**: `start_interview`, `start_language_test`, `start_general`, `audio_message`, `text_message`, `reset`

### `src/templates/index.html` — Frontend (~585 lines)
- **CSS**: Modern gradient UI, chat bubbles, pulse animation on mic
- **VAD Engine**: `getRMS()` + `startVAD()` — monitors microphone volume via `AnalyserNode`
- **Recording**: `startListening()` with `duringBotPlayback` flag for passive/active modes
- **Interruption**: Detects voice during bot playback → stops audio → tags message as interrupted
- **Auto-listen loop**: Bot `onended` → auto-starts mic → continuous conversation

---

## Setup & Installation

### Prerequisites
- Python 3.10+
- OpenAI API key with access to `gpt-4o-mini`, `whisper-1`, and `gpt-4o-mini-tts`

### Steps

```bash
# Clone the repository
git clone <repo-url>
cd "New Interview preparation Assistant"

# Create and activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set your OpenAI API key
# Option 1: Environment variable
set OPENAI_API_KEY=sk-your-key-here        # Windows
export OPENAI_API_KEY=sk-your-key-here      # Mac/Linux

# Option 2: Create .env file
echo OPENAI_API_KEY=sk-your-key-here > .env

# Run the app
python src/app.py
```

Open `http://127.0.0.1:5000` in your browser. Allow microphone access when prompted.

---

## Challenges & Solutions

### 1. Speech-to-Speech Latency
**Challenge**: The pipeline (record → upload → Whisper STT → GPT → TTS → download → play) has inherent latency. Users expect instant responses like a phone call.

**Solution**: 
- Used `gpt-4o-mini` instead of `gpt-4o` for faster inference
- Kept max_tokens low (150-300) to reduce generation time
- Used WebSocket (Socket.IO) instead of HTTP for lower overhead
- Chose MP3 over WAV for smaller audio payloads

### 2. Voice Activity Detection (VAD)
**Challenge**: Users don't want to click buttons to stop recording. The app needs to know when someone has finished speaking — but not cut them off during natural pauses.

**Solution**: 
- Implemented custom VAD using Web Audio API's `AnalyserNode`
- Calculated RMS (Root Mean Square) of audio samples every 100ms
- Required 1.5 seconds of continuous silence before auto-stopping — long enough to not cut off mid-thought, short enough to feel responsive
- Only triggers after speech is first detected (ignores pre-speech silence)

### 3. Voice Interruption During Bot Playback
**Challenge**: In a real conversation, you can interrupt someone. But the mic was only active after bot finished speaking, so you had to wait through the entire response.

**Solution**:
- Start mic in "passive listening" mode while bot audio plays (using `duringBotPlayback` flag to avoid stopping the audio)
- VAD monitors for user voice — when detected, immediately pauses bot audio
- Tags the user's message with `[INTERRUPTED]` prefix so GPT knows to acknowledge the interruption
- System prompts include specific instructions for handling interruptions naturally

### 4. Bot Sounding Robotic
**Challenge**: Early TTS output sounded flat and mechanical, breaking the illusion of a real conversation.

**Solution**:
- Switched from Google TTS (gTTS) to OpenAI's `gpt-4o-mini-tts` which supports an `instructions` parameter
- Created detailed, mode-specific voice instructions (e.g., "sound genuinely pleased when giving positive feedback", "laugh a little if something is funny")
- Used different voices per mode (coral/nova/shimmer) for variety
- Made GPT output more natural by adding filler words ("hmm", "yeah", "so") and varying reaction phrases
- Increased temperature to 0.9 for more varied, less formulaic responses

### 5. Bot Not Giving Feedback (Just Asking Next Question)
**Challenge**: The interview bot would skip evaluating the user's answer and jump straight to the next question.

**Solution**: 
- Restructured the system prompt to make feedback the #1 priority
- Added explicit response structure: "React to their answer FIRST (1-2 sentences), THEN ask next question"
- Added rules for different answer quality (correct → tip, partial → what's missing, wrong → explain correct answer)
- Increased max_tokens for interview mode (300) to allow room for feedback + question

### 6. API Key & Model Access Issues
**Challenge**: Got 403 errors for `gpt-4o` and `tts-1` — the project's API key had model-level restrictions.

**Solution**:
- Discovered project-level restrictions in OpenAI dashboard
- Switched all chat to `gpt-4o-mini` which was accessible
- Switched TTS from `tts-1` to `gpt-4o-mini-tts` (newer, better, with instructions support)
- Learned to verify model access before building features around specific models

### 7. Echo & Feedback Loop
**Challenge**: When the mic is active during bot audio playback, it could pick up the bot's own voice output, creating a feedback loop.

**Solution**:
- Enabled `echoCancellation: true` and `noiseSuppression: true` in `getUserMedia` constraints
- The browser's built-in echo cancellation handles most cases
- VAD threshold (RMS > 15) filters out low-level audio bleed

### 8. Conversation Context Overflow
**Challenge**: Long conversations accumulate too many messages, exceeding the model's context window and increasing costs.

**Solution**:
- Implemented sliding window: keep system prompt + last 20 messages
- Older messages are trimmed automatically after each response
- System prompt is always preserved as the first message

---

## How to Explain This Project

### Elevator Pitch (30 seconds)
> "I built a voice-to-voice AI interview preparation app using Python and OpenAI. You speak to it like you would to a real interviewer — it asks technical questions, listens to your answer, gives you instant feedback on what you got right or wrong, and then moves to the next question. It also has a language practice mode where you can chat with an AI native speaker in 13 languages. The key technical challenge was implementing real-time voice activity detection and interruption handling so the conversation feels completely natural."

### Technical Deep Dive (2 minutes)
> "The architecture is a Flask + Socket.IO backend with a vanilla JS frontend. Audio flows through a three-stage pipeline: the user's voice is captured via MediaRecorder as WebM/Opus, sent over WebSocket to the server where Whisper-1 transcribes it, GPT-4o-mini generates a contextual response using conversation history, and gpt-4o-mini-tts converts it to natural speech with mode-specific voice instructions. The response audio is base64-encoded and streamed back over WebSocket for immediate playback.
>
> The most interesting part is the VAD system — I use the Web Audio API's AnalyserNode to calculate RMS volume every 100ms. After 1.5 seconds of silence following detected speech, it auto-stops recording and sends the audio. During bot playback, the mic runs in passive mode — if it detects the user's voice, it immediately pauses the bot and captures the interruption. The message gets tagged as [INTERRUPTED] so the GPT model acknowledges it naturally instead of continuing its previous thought.
>
> Each mode has its own persona, voice, and detailed TTS instructions — the interview mode uses 'coral' voice with warm office-conversation instructions, language mode uses 'nova' with patient native-speaker energy, and free chat uses 'shimmer' with casual coffee-chat personality."

### Key Talking Points for Interviews
1. **Real-time WebSocket communication** — why Socket.IO over REST for audio streaming
2. **Three OpenAI models in one pipeline** — Whisper (STT) → GPT-4o-mini (reasoning) → gpt-4o-mini-tts (TTS)
3. **Custom Voice Activity Detection** — Web Audio API, `AnalyserNode`, RMS calculation, silence thresholds
4. **Prompt engineering** — detailed system prompts for personality, feedback structure, interruption handling
5. **Voice interruption architecture** — passive mic listening, `[INTERRUPTED]` tagging, graceful AI response
6. **Conversation memory management** — sliding window to balance context vs. token limits
7. **Mode-specific TTS instructions** — using `gpt-4o-mini-tts` instructions parameter for expressive, non-robotic speech

## License
This project is licensed under the MIT License.