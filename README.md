# Voice Interview Preparation Assistant

## Overview
The Voice Interview Preparation Assistant is a real-time, streaming speech-to-speech AI conversational bot. It is designed to simulate realistic interview practice, language speaking tests, and free-form voice conversations. The app uses OpenAI's latest models with a streaming LLM + chunked TTS pipeline, browser-native real-time STT, and emotional prosody control to create natural, human-like voice interaction with sub-second perceived latency.

## Key Features
- **Real-Time Interview Practice**: Get asked real technical questions, receive instant feedback, and guidance.
- **Language Practice**: Practice speaking in 13 languages with a patient native speaker.
- **Free Chat Mode**: Engage in casual conversations with a smart AI colleague.
- **Streaming LLM + TTS Pipeline**: Token-by-token LLM generation with progressive TTS for real-time responses.
- **Emotional Tone Tracking**: Detects conversation emotion and adjusts TTS prosody dynamically.
- **Instant Voice Interruption**: Interrupt the bot mid-sentence, and it stops instantly.
- **LLM-Powered Memory Compression**: Summarizes old conversation messages for better context retention.

## Tech Stack
- **Backend**: Python, Flask, Flask-SocketIO, Eventlet
- **Frontend**: Vanilla JavaScript, Web Speech API, Web Audio API
- **AI Models**: GPT-4o-mini, GPT-4o-mini-TTS, Whisper
- **Database**: PostgreSQL, Redis
- **Observability**: OpenTelemetry, Prometheus

## Setup & Installation

### Prerequisites
- Python 3.10+
- OpenAI API key with access to `gpt-4o-mini`, `whisper-1`, and `gpt-4o-mini-tts`

### Steps
1. Clone the repository:
   ```bash
   git clone https://github.com/amitsingla13/interview-prep-assistant
   cd "New Interview preparation Assistant"
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Mac/Linux:
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set your OpenAI API key:
   - Option 1: Environment variable
     ```bash
     set OPENAI_API_KEY=sk-your-key-here  # Windows
     export OPENAI_API_KEY=sk-your-key-here  # Mac/Linux
     ```
   - Option 2: Create a `.env` file:
     ```bash
     echo OPENAI_API_KEY=sk-your-key-here > .env
     ```

5. Run the app:
   ```bash
   python src/app.py
   ```
   Open `http://127.0.0.1:5000` in your browser and allow microphone access when prompted.

## Deployment

### Apple App Store and Google Play Store Compatibility
- Ensure the app complies with Apple and Google guidelines for app submission.
- Use a framework like React Native or Flutter for cross-platform compatibility.
- Follow the respective store's requirements for privacy, security, and user experience.

### Enterprise Setup (Optional)
Enable enterprise features by setting the corresponding environment variables:

- **Redis**: Session store, TTS cache, rate limiting
  ```bash
  REDIS_URL=redis://localhost:6379/0
  ```

- **PostgreSQL**: Persistent storage for users, conversations, and analytics
  ```bash
  DATABASE_URL=postgresql://user:pass@localhost:5432/interview_app
  ```

- **JWT Authentication**:
  ```bash
  AUTH_ENABLED=true
  JWT_SECRET_KEY=your-secret-key-here
  JWT_ACCESS_TOKEN_EXPIRES=3600
  JWT_REFRESH_TOKEN_EXPIRES=2592000
  ```

- **OpenTelemetry Tracing**:
  ```bash
  OTEL_ENABLED=true
  OTEL_SERVICE_NAME=voice-interview-assistant
  OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
  ```

- **Prometheus Metrics**:
  ```bash
  PROMETHEUS_ENABLED=true
  PROMETHEUS_PORT=9090
  ```

## License
This project is licensed under the MIT License.