# Voice Interview Preparation Assistant

A **real-time, streaming speech-to-speech AI conversational bot** built with Python that simulates realistic interview practice, language speaking tests, and free-form voice conversations. The app uses OpenAI's latest models with a **streaming LLM + chunked TTS pipeline**, **browser-native real-time STT**, and **emotional prosody control** to create natural, human-like voice interaction with sub-second perceived latency. Think of it as having a friendly colleague you can practice with anytime.

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

The entire interaction is **streaming speech-to-speech**: you speak and the AI begins responding with voice in real-time — words appear and audio plays progressively as the AI thinks. You can **interrupt mid-sentence** and the bot stops instantly. It feels like a real phone call.

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Streaming LLM + TTS Pipeline** | Token-by-token LLM generation → multi-sentence chunking → progressive TTS → audio plays while AI is still thinking |
| **Browser SpeechRecognition STT** | Uses the Web Speech API for **instant** real-time transcription (no upload delay) with Whisper as fallback |
| **Instant Voice Interruption** | Interrupt the bot in 300ms — cancels active LLM generation + TTS + flushes audio buffer immediately |
| **Emotional Tone Tracking** | Detects conversation emotion (empathetic/enthusiastic/curious/serious/encouraging) and adjusts TTS prosody dynamically |
| **Enhanced TTS Prosody** | Breath modeling, micro-pauses, trailing intonation, emotional modifiers — sounds like a real person, not a robot |
| **LLM-Powered Memory Compression** | Old conversation messages are summarized by GPT into a compact context instead of simple truncation |
| **Cancellation Controller** | Backend cancellation tokens allow instant abort of any active LLM + TTS generation on user interrupt |
| **Voice Activity Detection (VAD)** | Automatically detects when you stop talking (1.5s silence) — no button clicking needed |
| **3 Distinct Modes** | IT Interview, Language Speaking Test, Free Chat — each with its own personality, voice, and behavior |
| **13 Language Support** | English, Spanish, French, German, Chinese, Hindi, Japanese, Korean, Portuguese, Arabic, Russian, Italian, Dutch |
| **Auto-listen Loop** | After the bot finishes speaking, it automatically starts listening again — hands-free conversation flow |
| **Progressive Audio Playback** | Audio chunks queued and played sequentially — first audio arrives within ~1s of user finishing speaking |
| **Text + Voice Input** | Supports both typing and voice input for flexibility |
| **Mode-specific TTS Voices** | Different OpenAI voices per mode (coral/shimmer/ash) with tailored emotional speech instructions |

---

## Architecture & How It Works

```
┌──────────────────────────────────────────────────────────────────────┐
│                        BROWSER (Frontend)                            │
│                                                                      │
│  ┌────────────────┐  ┌─────────────────┐  ┌───────────────────────┐ │
│  │ SpeechRecognit- │  │  MediaRecorder   │  │  Streaming Audio     │ │
│  │ ion API (fast)  │  │  + Whisper (fb)  │  │  Chunk Queue         │ │
│  │ Instant STT     │  │  WebM/Opus       │  │  Progressive Play    │ │
│  └──────┬──────────┘  └──────┬──────────┘  └──────▲──────────────┘ │
│         │ text_message       │ audio_message       │                 │
│         │ (instant)          │ (fallback)           │ audio_chunk    │
│  ┌──────▼────────────────────▼──────────┐  ┌───────┴──────────────┐ │
│  │  Socket.IO (emit)                     │  │  Socket.IO (listen)  │ │
│  │  + cancel_stream on interrupt         │  │  text_chunk          │ │
│  └──────────────┬────────────────────────┘  │  audio_chunk         │ │
│                 │                            │  stream_complete     │ │
│  ┌──────────────┴────────────────────────┐  └───────▲──────────────┘ │
│  │  VAD Engine (Web Audio API)           │          │                │
│  │  RMS analysis @ 50ms intervals        │          │                │
│  │  Silence: 1.5s → auto-stop            │          │                │
│  │  Interrupt: 300ms speech → cancel      │          │                │
│  └───────────────────────────────────────┘          │                │
└────────────────────┼────────────────────────────────┼────────────────┘
                     │  WebSocket (real-time)          │
┌────────────────────▼────────────────────────────────┼────────────────┐
│                    FLASK SERVER (Backend)                             │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │              Socket.IO Handlers + Cancellation Controller      │  │
│  │  audio_message │ text_message │ cancel_stream │ start_* │ reset│  │
│  │  active_generations{sid: cancel_token} — instant abort support │  │
│  └───────┬────────┴───────┬──────┴───────────────────────────────┘  │
│          │                │                                          │
│  ┌───────▼────────┐      │ (fast path: text already transcribed)    │
│  │ 1. WHISPER STT │      │                                          │
│  │ (whisper-1)    │      │                                          │
│  │ fallback only  │◄─────┘                                          │
│  └───────┬────────┘                                                  │
│          │ user_text                                                  │
│  ┌───────▼────────────────────────────────────────────────────────┐  │
│  │ 2. EMOTIONAL TONE DETECTION                                    │  │
│  │    Tracks: empathetic/enthusiastic/curious/serious/encouraging  │  │
│  │    Feeds into TTS prosody modifiers dynamically                │  │
│  └───────┬────────────────────────────────────────────────────────┘  │
│          │                                                           │
│  ┌───────▼──────────────────────────────────┐                       │
│  │ 3. STREAMING GPT CHAT (gpt-4o-mini)      │                       │
│  │    Token-by-token streaming generation    │  ◄── cancel_token    │
│  │    + sentence boundary detection          │      checked per     │
│  │    + multi-sentence chunk grouping        │      token           │
│  └───────┬──────────────────────────────────┘                       │
│          │ sentence chunks (2-3 sentences)                           │
│  ┌───────▼──────────────────────────────────┐                       │
│  │ 4. STREAMING TTS (gpt-4o-mini-tts)       │                       │
│  │    Emotional prosody + breath modeling    │  ◄── cancel_token    │
│  │    Per-chunk Opus audio generation        │      checked per     │
│  │    Emits: text_chunk + audio_chunk        │      chunk           │
│  └───────┬──────────────────────────────────┘                       │
│          │ progressive emission                                      │
│  ┌───────▼──────────────────────────────────┐                       │
│  │ 5. LLM MEMORY COMPRESSION               │                       │
│  │    GPT summarizes old messages (>20)     │                       │
│  │    into 3-5 sentence context summary     │                       │
│  └──────────────────────────────────────────┘                       │
└──────────────────────────────────────────────────────────────────────┘
```

### Data Flow — Streaming Pipeline (per user message):
1. **User speaks** → Browser's SpeechRecognition API transcribes in real-time (instant text) OR MediaRecorder captures audio as WebM/Opus (fallback)
2. **VAD detects silence** (~1.5s after speech) → auto-stops recording
3. **Fast path**: If browser STT produced text, sends it directly as `text_message` — **no audio upload, no Whisper, near-zero latency**
4. **Slow path (fallback)**: Audio sent via Socket.IO → Whisper transcribes server-side
5. **Emotional tone detected** from conversation context → feeds into TTS prosody
6. **GPT-4o-mini streams** response token-by-token → sentence boundary detection groups 2-3 sentences per chunk
7. **First chunk (1 sentence)** sent immediately for fast time-to-first-audio (~1s)
8. **gpt-4o-mini-tts** generates Opus audio per chunk with emotional prosody instructions
9. **Audio chunks emitted progressively** via Socket.IO → browser queues and plays sequentially
10. **Cancellation controller** checks cancel token after every LLM token and TTS chunk — user interrupt aborts entire pipeline instantly
11. **Mic auto-starts** → continuous conversation loop

### Interruption Flow:
1. User speaks during bot playback → VAD detects voice (300ms threshold)
2. Frontend emits `cancel_stream` → stops all audio → flushes chunk queue
3. Backend receives cancel → sets `cancel_token['cancelled'] = True`
4. Active LLM streaming + TTS generation abort immediately
5. Frontend starts fresh recording — near-zero delay to new listening

---

## Tech Stack

### Backend — Core
| Technology | Purpose | Why Chosen |
|-----------|---------|------------|
| **Python 3.13** | Core language | Rich AI/ML ecosystem, OpenAI SDK support |
| **Flask** | Web framework | Lightweight, perfect for single-page app |
| **Flask-SocketIO** | WebSocket communication | Real-time bidirectional streaming, much faster than HTTP polling |
| **eventlet** | Async worker | Non-blocking I/O for concurrent WebSocket + streaming LLM |
| **OpenAI Python SDK (v1.0+)** | API client | Modern streaming-compatible client for GPT, Whisper, and TTS |
| **python-dotenv** | Environment config | Secure API key management |
| **tempfile** | Temp file handling | Whisper API requires file input, so audio bytes are written to temp `.webm` files |

### Backend — Enterprise (all optional, graceful fallback)
| Technology | Purpose | Why Chosen |
|-----------|---------|------------|
| **Redis** | Session store, TTS cache, rate limiting | Sub-ms latency, sliding-window rate limits via sorted sets, scales horizontally |
| **PostgreSQL + SQLAlchemy** | Persistent storage (users, conversations, analytics) | ACID-compliant, powerful ORM, production-proven at scale |
| **Celery** | Async task queues (4 queues: stt, llm, tts, analytics) | Offload heavy work, auto-retry, worker pool management |
| **JWT Auth (pure Python)** | Authentication & authorization | Stateless tokens, PBKDF2-SHA256 passwords, no external dependency |
| **OpenTelemetry** | Distributed tracing | OTLP export, Flask auto-instrumentation, trace correlation |
| **Prometheus** | Metrics (17 custom metrics) | Industry-standard monitoring: STT/LLM/TTS latency, TTFA, errors, cache hits |
| **Structured Logging** | JSON-formatted logs | Request ID correlation, trace/span IDs, machine-parseable for ELK/Loki |
| **Middleware** | Request lifecycle (ID, timing, security headers) | HSTS, CSP, X-Request-ID tracking, response timing |

### Frontend
| Technology | Purpose | Why Chosen |
|-----------|---------|------------|
| **Vanilla JavaScript** | UI logic | No framework overhead, direct browser API access |
| **Socket.IO Client 4.7** | WebSocket client | Matches Flask-SocketIO for reliable real-time streaming |
| **Web Speech API** | Real-time STT | `SpeechRecognition` for instant browser-native transcription — eliminates Whisper upload delay |
| **Web Audio API** | Voice Activity Detection | `AudioContext` + `AnalyserNode` for real-time RMS-based microphone monitoring |
| **MediaRecorder API** | Audio capture (fallback) | Browser-native recording in WebM/Opus format for Whisper STT |
| **HTML5 Audio + AudioContext** | Streaming playback | Queued playback of progressive audio chunks from streaming TTS |
| **Font Awesome 6.5** | Icons | Clean UI icons for mic, send, modes |
| **CSS3 Gradients + Animations** | Modern UI | Gradient backgrounds, pulse animation on mic button during recording |

### Communication
| Layer | Protocol | Format |
|-------|----------|--------|
| Client ↔ Server | **WebSocket** (Socket.IO) | JSON events with base64 audio payloads, streaming text/audio chunks |
| Server → OpenAI | **HTTPS REST (streaming)** | OpenAI SDK handles chunked transfer encoding for streaming |
| STT (fast path) | **Browser-native** | Web Speech API → text sent as `text_message` (no upload) |
| STT (fallback) | **WebSocket upload** | WebM/Opus → base64 → Whisper API (for non-English) |
| Audio encoding | **WebM/Opus** (upload) → **Opus** (response) | Opus for efficient capture and compact streaming playback |

---

## LLM Models Used

### 1. `gpt-4o-mini` — Chat/Reasoning (Streaming)
- **Used for**: Generating interview questions, evaluating answers, providing feedback, conversation
- **Streaming**: Token-by-token generation with sentence boundary detection for progressive responses
- **Temperature**: 0.85 (natural variance without being random)
- **Max tokens**: 300 (interview), 150 (language/general) — keeps responses concise
- **Cancel support**: Checked per-token — aborts immediately on user interrupt

### 2. `whisper-1` — Speech-to-Text (Fallback)
- **Used for**: Transcribing user's voice when browser SpeechRecognition is unavailable (non-English, unsupported browsers)
- **Input**: WebM/Opus audio files
- **Primary STT**: Browser's `SpeechRecognition` API handles English (instant, no upload)
- **Multi-language**: Whisper auto-detects the language spoken

### 3. `gpt-4o-mini-tts` — Text-to-Speech (Streaming Chunks)
- **Used for**: Converting bot text responses to natural human-like voice with emotional prosody
- **Key features**: 
  - `instructions` parameter for controlling voice expressiveness, breath modeling, micro-pauses
  - Emotional tone modifiers dynamically appended based on conversation context
  - Multi-sentence chunking (2-3 sentences per TTS call for natural prosody flow)
- **Format**: Opus (compact, low-latency streaming)
- **Voices used**:
  - `coral` — Interview mode (warm, professional)
  - `shimmer` — Language mode (clear, friendly)
  - `ash` — Free chat mode (casual, approachable)
- **Emotional modifiers**: Automatically adjusts to empathetic/enthusiastic/curious/serious/encouraging tones

---

## Feature Breakdown

### 1. Streaming LLM + TTS Pipeline
| Aspect | Implementation |
|--------|---------------|
| **LLM streaming** | Token-by-token generation via OpenAI streaming API |
| **Sentence detection** | Splits at `.!?` boundaries with minimum length thresholds |
| **Chunk grouping** | First chunk = 1 sentence (fast TTFA), subsequent = 2-3 sentences (better prosody) |
| **TTS per chunk** | Each sentence group → `gpt-4o-mini-tts` with emotional prosody instructions |
| **Progressive emit** | `text_chunk` + `audio_chunk` events sent as each chunk completes |
| **Frontend queue** | `audioChunkQueue` plays chunks sequentially without gaps |
| **Cancel support** | Cancel token checked after every LLM token and every TTS chunk generation |
| **First audio latency** | ~1 second from user finishing speaking to hearing first bot audio |

### 2. Browser SpeechRecognition (Instant STT)
| Aspect | Implementation |
|--------|---------------|
| **API** | `window.SpeechRecognition` / `webkitSpeechRecognition` (Web Speech API) |
| **Mode** | Continuous recognition with interim results for live feedback |
| **Scope** | Used for English modes (Interview, Free Chat) — instant text, no upload |
| **Fallback** | Language mode + unsupported browsers → MediaRecorder + Whisper |
| **Latency benefit** | Eliminates 2-4 seconds of record→encode→upload→Whisper pipeline |
| **Live transcription** | Shows partial transcription in status bar as user speaks |

### 3. IT Interview Practice Mode
| Aspect | Implementation |
|--------|---------------|
| **Persona** | "Alex" — senior engineering manager |
| **System prompt** | Detailed instructions for feedback-first responses, natural filler words, varied reactions |
| **Topics** | System design, coding concepts, behavioral, cloud/DevOps, databases |
| **Feedback loop** | Evaluates every answer → correct/partial/wrong → explains why → next question |
| **Voice** | `coral` with warm office-conversation TTS instructions + emotional modifiers |
| **Conversation cues** | Handles "wait", "skip", "repeat", "I don't know" naturally |

### 4. Language Speaking Test Mode
| Aspect | Implementation |
|--------|---------------|
| **13 languages** | EN, ES, FR, DE, ZH, HI, JA, KO, PT, AR, RU, IT, NL |
| **Persona** | Native speaker friend |
| **Error correction** | Gentle inline corrections ("Almost! You'd usually say...") |
| **Dynamic prompt** | System prompt template with `{language}` placeholder filled at runtime |
| **Voice** | `shimmer` with patient native-speaker TTS instructions |
| **STT** | Uses Whisper for accurate multi-language transcription (not browser STT) |

### 5. Free Chat Mode
| Aspect | Implementation |
|--------|---------------|
| **Persona** | Smart casual colleague |
| **Behavior** | Matches user's energy, responds in user's language |
| **Voice** | `ash` with casual coffee-chat TTS instructions |
| **Use case** | General conversation practice, Q&A, brainstorming |

### 6. Voice Activity Detection (VAD)
| Aspect | Implementation |
|--------|---------------|
| **Technology** | Web Audio API — `AudioContext` + `AnalyserNode` |
| **Detection method** | RMS (Root Mean Square) volume analysis every 50ms |
| **Silence threshold** | RMS < 15 (on 0-128 scale) = silence |
| **Auto-stop trigger** | 1.5 seconds of continuous silence after speech detected |
| **Result** | Hands-free: click mic once, then just talk naturally |

### 7. Instant Voice Interruption
| Aspect | Implementation |
|--------|---------------|
| **Interrupt detection** | 300ms of speech during bot playback triggers interrupt |
| **Frontend action** | Emits `cancel_stream` → stops all audio → flushes chunk queue → starts recording |
| **Backend action** | Sets `cancel_token['cancelled'] = True` → LLM + TTS abort immediately |
| **AI response** | Interrupted messages tagged `[INTERRUPTED]` → AI acknowledges naturally |
| **Delay** | Near-zero — recording starts immediately after interrupt (no timeout) |

### 8. Emotional Tone Tracking
| Aspect | Implementation |
|--------|---------------|
| **Detection** | Rule-based classification from conversation content |
| **Tones** | empathetic, enthusiastic, curious, serious, encouraging, neutral |
| **Application** | Dynamically modifies TTS `instructions` parameter per chunk |
| **Examples** | Sad user → empathetic warmth; excited → enthusiastic energy; confused → encouraging patience |

### 9. Enhanced TTS Prosody
| Aspect | Implementation |
|--------|---------------|
| **Breath modeling** | Instructions include natural breath points and micro-pauses |
| **Trailing intonation** | Sentences end with natural trailing pitch, not abrupt stops |
| **Filler words** | GPT prompted to include "hmm", "well", "so" for natural flow |
| **Emotional modifiers** | Tone-specific instructions appended (e.g., "add genuine warmth", "sound curious") |
| **Multi-sentence chunks** | 2-3 sentences per TTS call preserves natural prosody and intonation flow |

### 10. LLM-Powered Memory Compression
| Aspect | Implementation |
|--------|---------------|
| **Trigger** | When conversation exceeds 20 messages |
| **Method** | GPT-4o-mini summarizes old messages into 3-5 sentence context |
| **Preservation** | System prompt always kept; recent 10 messages preserved verbatim |
| **Benefit** | Better context retention than simple truncation; lower token usage |

---

## Project Structure

```
├── src/
│   ├── app.py                 # Flask backend — streaming pipeline, API calls, Socket.IO handlers
│   ├── config.py              # Centralized environment-based config (Dev/Staging/Prod)
│   ├── redis_store.py         # Redis session store, TTS cache, sliding-window rate limiter
│   ├── database.py            # PostgreSQL models (User, Conversation, Message, Analytics)
│   ├── auth.py                # JWT authentication — register/login/refresh, pure Python tokens
│   ├── workers.py             # Celery task queues (stt, llm, tts, analytics)
│   ├── observability.py       # OpenTelemetry tracing, Prometheus metrics, structured logging
│   ├── middleware.py           # Request ID, response timing, security headers (HSTS, CSP)
│   ├── voice/
│   │   └── openai_voice.py    # Helper functions for Whisper STT and OpenAI TTS
│   ├── static/
│   │   ├── voice.js           # On-demand TTS playback helpers
│   │   ├── manifest.json      # PWA manifest
│   │   └── sw.js              # Service worker for PWA
│   ├── templates/
│   │   ├── index.html         # Frontend — UI, STT, VAD, streaming audio, Socket.IO client
│   │   ├── privacy.html       # Privacy policy page
│   │   └── terms.html         # Terms of service page
│   └── data/                  # Knowledge base data files
├── requirements.txt           # Python dependencies (core + optional enterprise)
├── README.md                  # This file
├── render.yaml                # Render deployment config
├── .venv/                     # Python virtual environment
└── .env                       # API key + enterprise config — not committed
```

### `src/app.py` — Backend (~1500+ lines)
- **System Prompts**: 3 detailed prompts (interview, language, general) with personality, rules, and interruption handling
- **Cancellation Controller**: `active_generations` dict with per-session cancel tokens, checked per LLM token
- **Emotional Tone Detection**: `detect_emotional_tone()` — rule-based classification feeding TTS prosody
- **Enterprise Integration**: Redis session store, PostgreSQL logging, JWT auth, Celery dispatch, OpenTelemetry tracing, Prometheus metrics
- **Health Checks**: `/health` (dependencies), `/health/ready` (readiness probe), `/health/live` (liveness probe)
- **API Endpoints**: `/api/analytics`, `/api/metrics`, `/api/config` (frontend VAD settings)
- **`transcribe_audio()`**: Saves WebM bytes to temp file → calls Whisper API → returns text
- **`generate_speech()`**: Calls gpt-4o-mini-tts with mode-specific voice + emotional prosody instructions → returns Opus bytes
- **`stream_chat_and_speak()`**: Core streaming pipeline — token-by-token LLM → sentence grouping → per-chunk TTS → progressive emit
- **`chat_with_gpt()`**: Non-streaming GPT call (used for text-only mode)
- **`summarize_old_messages()`**: LLM-powered memory compression — GPT summarizes old messages into compact context
- **`process_and_respond()`**: Orchestrates the full pipeline with streaming for voice, non-streaming for text
- **Socket.IO handlers**: `start_interview`, `start_language_test`, `start_general`, `audio_message`, `text_message`, `cancel_stream`, `reset`

### Enterprise Modules (all optional — graceful fallback when unavailable)
- **`src/config.py`**: BaseConfig/DevelopmentConfig/StagingConfig/ProductionConfig classes; all settings from environment variables
- **`src/redis_store.py`**: Redis-backed sessions with in-memory fallback; TTS cache (Redis hash or dict); sliding-window rate limiter (Redis sorted sets)
- **`src/database.py`**: SQLAlchemy ORM models — User, Conversation, ConversationMessage, AnalyticsEvent; full CRUD + analytics queries
- **`src/auth.py`**: Pure Python JWT (HMAC-SHA256), PBKDF2-SHA256 passwords; `require_auth`/`require_admin` decorators; REST endpoints + Socket.IO auth
- **`src/workers.py`**: Celery with 4 dedicated queues; tasks: `transcribe_audio_task`, `generate_chat_response_task`, `generate_speech_task`, `analyze_conversation_task`
- **`src/observability.py`**: JSONFormatter logging, OpenTelemetry TracerProvider, 17 Prometheus metrics (STT/LLM/TTS duration, TTFA, errors, cache, interruptions)
- **`src/middleware.py`**: Before/after request hooks — X-Request-ID, X-Response-Time, HSTS, CSP, X-Content-Type-Options

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

### Enterprise Setup (Optional)

All enterprise features are **opt-in** — the app runs perfectly with just `OPENAI_API_KEY`. Enable features by setting the corresponding environment variables:

```bash
# ── Redis (session store + TTS cache + rate limiting) ──
REDIS_URL=redis://localhost:6379/0

# ── PostgreSQL (persistent users, conversations, analytics) ──
DATABASE_URL=postgresql://user:pass@localhost:5432/interview_app

# ── JWT Authentication ──
AUTH_ENABLED=true
JWT_SECRET_KEY=your-secret-key-here       # CHANGE in production
JWT_ACCESS_TOKEN_EXPIRES=3600             # 1 hour (seconds)
JWT_REFRESH_TOKEN_EXPIRES=2592000         # 30 days

# ── Celery Worker Pools ──
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
# Start workers:   celery -A src.workers worker -Q stt,llm,tts,analytics -c 4

# ── OpenTelemetry Tracing ──
OTEL_ENABLED=true
OTEL_SERVICE_NAME=voice-interview-assistant
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# ── Prometheus Metrics ──
PROMETHEUS_ENABLED=true
# Scrape endpoint:  GET /api/metrics

# ── Rate Limiting ──
RATE_LIMIT_RPM=30                         # Requests per minute
RATE_LIMIT_RPH=200                        # Requests per hour

# ── Environment ──
FLASK_ENV=production                      # development | staging | production
```

### Health Check Endpoints

| Endpoint | Purpose | Response |
|----------|---------|----------|
| `GET /health` | Full dependency health | Redis, DB, Celery status + metrics summary |
| `GET /health/ready` | Kubernetes readiness probe | 200 if app can serve traffic |
| `GET /health/live` | Kubernetes liveness probe | 200 if process is alive |
| `GET /api/metrics` | Prometheus metrics summary | Counters, histograms, latency budget |
| `GET /api/analytics` | Analytics dashboard data | Conversation stats, usage trends |

---

## Enterprise Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          BROWSER (Frontend)                              │
│   SpeechRecognition │ VAD │ Audio Queue │ JWT Token │ /api/config fetch  │
└─────────┬────────────────────────────────────────────────┬───────────────┘
          │  WebSocket (Socket.IO)                         │ REST API
┌─────────▼────────────────────────────────────────────────▼───────────────┐
│                       FLASK SERVER + MIDDLEWARE                            │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │ Request ID │ Timing │ Security Headers │ JWT Auth │ Rate Limiting   │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
│                                                                           │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────────────┐   │
│  │  Whisper    │  │ GPT Stream │  │ TTS Stream │  │ Observability    │   │
│  │  STT        │  │ gpt-4o-mini│  │ gpt-4o-tts │  │ Traces + Metrics │   │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └──────┬───────────┘   │
│        │               │               │                │                │
│  ┌─────▼───────────────▼───────────────▼────────────────▼──────────────┐ │
│  │              CELERY TASK QUEUES (optional)                           │ │
│  │  stt queue │ llm queue │ tts queue │ analytics queue                 │ │
│  └─────────────────────────────────────────────────────────────────────┘ │
└────────┬──────────────────────────┬──────────────────────┬───────────────┘
         │                          │                      │
┌────────▼────────┐  ┌──────────────▼───────┐  ┌──────────▼─────────────┐
│     REDIS        │  │    POSTGRESQL         │  │  OPENTELEMETRY         │
│  Sessions        │  │  Users                │  │  OTLP Exporter         │
│  TTS Cache       │  │  Conversations        │  │  → Jaeger / Tempo      │
│  Rate Limits     │  │  Messages             │  │                        │
│  Celery Broker   │  │  Analytics Events     │  │  PROMETHEUS            │
│                  │  │                       │  │  17 custom metrics     │
└──────────────────┘  └───────────────────────┘  └────────────────────────┘
```

---

## Challenges & Solutions

### 1. Speech-to-Speech Latency (Record → Upload → Whisper → GPT → TTS → Play)
**Challenge**: The original pipeline (record → upload blob → Whisper STT → GPT → TTS → download → play) had ~3-5 seconds of latency. Users expected instant responses like a phone call.

**Solution — Three-pronged attack**:
- **Browser SpeechRecognition**: Replaced the Whisper upload pipeline with the Web Speech API for English. Text is available as the user speaks — no audio encoding, no upload, no Whisper API call. Eliminates 2-4 seconds instantly.
- **Streaming LLM + TTS**: Instead of waiting for the full GPT response before generating TTS, tokens stream in real-time. As soon as 1 sentence completes, TTS generates and audio plays — user hears the first words ~1 second after speaking.
- **Faster VAD tuning**: Reduced silence detection from 2.5s to 1.5s — the app responds faster after the user stops speaking.

### 2. Robotic/Fragmented TTS Sound
**Challenge**: Single-sentence TTS chunking made each sentence sound disconnected — prosody, intonation, and rhythm reset with every sentence.

**Solution**:
- **Multi-sentence chunking**: Group 2-3 sentences per TTS call (first chunk = 1 sentence for fast TTFA, subsequent = 2-3 for natural prosody flow)
- **Emotional tone tracking**: Rule-based emotion detection (empathetic/enthusiastic/curious/serious/encouraging) feeds dynamic prosody modifiers into TTS instructions
- **Enhanced TTS instructions**: Added breath modeling, micro-pauses, trailing intonation, and natural filler direction to all mode-specific TTS prompts
- **Opus format**: Switched from MP3 to Opus for more natural-sounding compressed audio

### 3. Slow Interruption (User Had to Speak 800ms Before Bot Stopped)
**Challenge**: Users expected to interrupt the bot instantly, but the 800ms speech threshold + 200ms post-interrupt delay made it feel sluggish.

**Solution**:
- Reduced `INTERRUPT_SPEECH_MIN_MS` from 800 to 300ms — interruption triggers 2.5x faster
- Removed the 200ms `setTimeout` delay after interrupt — recording starts immediately
- Added backend **cancellation controller**: `active_generations` dict with cancel tokens checked per-token during streaming. When user interrupts, the active LLM generation + TTS call abort immediately instead of continuing in the background.

### 4. Conversation Context Overflow
**Challenge**: Long conversations accumulate too many messages, exceeding the model's context window and increasing costs. Simple truncation loses important context.

**Solution**:
- **LLM-powered memory compression**: When messages exceed 20, GPT-4o-mini summarizes old messages into a 3-5 sentence context summary
- Preserves system prompt + last 10 messages verbatim
- Summary inserted as a system message — maintains context quality while reducing token count by ~80%

### 5. Voice Activity Detection (VAD)
**Challenge**: Users don't want to click buttons to stop recording. The app needs to know when someone has finished speaking — but not cut them off during natural pauses.

**Solution**: 
- Custom VAD using Web Audio API's `AnalyserNode` — calculates RMS every 50ms
- 1.5 seconds of continuous silence triggers auto-stop (balanced: doesn't cut off mid-thought, responsive enough)
- Only triggers after speech is first detected (ignores pre-speech silence)
- Separate interrupt monitor during bot playback with lower threshold

### 6. Bot Not Giving Feedback (Just Asking Next Question)
**Challenge**: The interview bot would skip evaluating the user's answer and jump straight to the next question.

**Solution**: 
- Restructured the system prompt to make feedback the #1 priority
- Added explicit response structure: "React to their answer FIRST (1-2 sentences), THEN ask next question"
- Added rules for different answer quality (correct → tip, partial → what's missing, wrong → explain correct answer)
- Increased max_tokens for interview mode (300) to allow room for feedback + question

### 7. Echo & Feedback Loop
**Challenge**: When the mic is active during bot audio playback, it could pick up the bot's own voice output, creating a feedback loop.

**Solution**:
- Enabled `echoCancellation: true` and `noiseSuppression: true` in `getUserMedia` constraints
- Separate interrupt threshold (RMS > 30) higher than normal speech detection (RMS > 15) to filter speaker echo
- The browser's built-in echo cancellation handles most cases

---

## How to Explain This Project

### Elevator Pitch (30 seconds)
> "I built a streaming voice-to-voice AI interview preparation app using Python and OpenAI. You speak to it naturally — it transcribes in real-time using the browser's Speech API, streams its response token-by-token through GPT, and plays audio progressively as it thinks — you hear the first words within a second. You can interrupt it mid-sentence and it stops instantly. It tracks emotional tone and adjusts its voice style dynamically. It also has a language practice mode for 13 languages. The key technical challenges were building the streaming LLM+TTS pipeline, instant cancellation, and making TTS sound human through multi-sentence chunking and prosody control."

### Technical Deep Dive (2 minutes)
> "The architecture is a Flask + Flask-SocketIO backend with eventlet for async I/O, and a vanilla JS frontend with multiple browser APIs. The core innovation is a **streaming pipeline** — instead of the traditional record→transcribe→generate→speak sequential approach, everything runs in parallel:
>
> For STT, I use the browser's SpeechRecognition API which gives instant text as the user speaks — no audio upload, no Whisper API call. This alone eliminates 2-4 seconds of latency. Whisper is kept as a fallback for non-English languages.
>
> For generation, GPT-4o-mini streams tokens in real-time. I detect sentence boundaries and group them into chunks of 2-3 sentences (first chunk is 1 sentence for fast time-to-first-audio). Each chunk is sent to gpt-4o-mini-tts for voice generation with emotional prosody instructions — the system tracks the conversation's emotional tone and dynamically adjusts TTS instructions to sound empathetic, enthusiastic, or encouraging as appropriate.
>
> Audio chunks are emitted progressively via Socket.IO and queued on the frontend for gapless playback. The user hears the bot start speaking about 1 second after they stop talking.
>
> For interruption, I built a cancellation controller — each session has a cancel token that's checked after every LLM token and every TTS chunk. When the user speaks for 300ms during bot playback, the frontend emits `cancel_stream`, the backend aborts the active generation immediately, and the frontend flushes its audio queue and starts fresh recording — essentially instant interruption.
>
> Memory management uses LLM-powered compression — when conversations exceed 20 messages, GPT summarizes old context into a 3-5 sentence digest instead of simple truncation."

### Key Talking Points for Interviews
1. **Streaming pipeline architecture** — token-level LLM streaming → sentence grouping → progressive TTS → chunked audio playback
2. **Dual STT strategy** — Browser SpeechRecognition (instant, zero-latency) with Whisper fallback (multi-language accuracy)
3. **Cancellation controller** — per-session cancel tokens checked per-token for instant abort on interruption
4. **Emotional prosody system** — rule-based tone detection → dynamic TTS instruction modification
5. **Multi-sentence TTS chunking** — 2-3 sentences per chunk for natural prosody vs single-sentence fragmentation
6. **LLM-powered memory compression** — GPT summarization of old messages vs simple sliding window
7. **WebSocket real-time communication** — Socket.IO for bidirectional streaming of text chunks + audio chunks
8. **Voice Activity Detection** — Custom RMS-based VAD with separate thresholds for speech detection vs bot-interrupt
9. **Three OpenAI models in one pipeline** — Whisper (STT) → GPT-4o-mini (streaming reasoning) → gpt-4o-mini-tts (emotional TTS)
10. **Progressive UX** — user sees text appear and hears audio play while AI is still generating the rest of the response

## License
This project is licensed under the MIT License.