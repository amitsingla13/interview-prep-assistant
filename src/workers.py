"""
Celery Worker Pools
====================
Async task queues for STT, LLM, and TTS operations with dedicated worker pools.
Blueprint Section 9: Scalability — worker pool separation for compute-intensive tasks.

Requires Redis as message broker. Gracefully disabled when CELERY_BROKER_URL is not set.
"""
import os
import time
import base64
import logging
import tempfile

logger = logging.getLogger(__name__)

_celery_app = None
_celery_available = False


def init_celery(config):
    """Initialize Celery app with configuration. Returns celery app or None."""
    global _celery_app, _celery_available

    if not config.CELERY_ENABLED:
        logger.info("[Celery] CELERY_BROKER_URL not configured — async workers disabled")
        return None

    try:
        from celery import Celery

        _celery_app = Celery(
            'interview_prep',
            broker=config.CELERY_BROKER_URL,
            backend=config.CELERY_RESULT_BACKEND,
        )

        _celery_app.conf.update(
            # Task settings
            task_serializer='json',
            accept_content=['json'],
            result_serializer='json',
            timezone='UTC',
            enable_utc=True,

            # Worker settings
            worker_prefetch_multiplier=1,  # One task at a time per worker
            worker_max_tasks_per_child=100,  # Restart worker after 100 tasks (memory leak prevention)
            worker_max_memory_per_child=512000,  # 512MB max memory per worker

            # Routing: separate queues for STT, LLM, TTS
            task_routes={
                'workers.transcribe_audio_task': {'queue': 'stt'},
                'workers.generate_chat_response_task': {'queue': 'llm'},
                'workers.generate_speech_task': {'queue': 'tts'},
                'workers.analyze_conversation_task': {'queue': 'analytics'},
            },

            # Queue definitions
            task_queues={
                'stt': {'exchange': 'stt', 'routing_key': 'stt'},
                'llm': {'exchange': 'llm', 'routing_key': 'llm'},
                'tts': {'exchange': 'tts', 'routing_key': 'tts'},
                'analytics': {'exchange': 'analytics', 'routing_key': 'analytics'},
                'default': {'exchange': 'default', 'routing_key': 'default'},
            },

            # Result expiration
            result_expires=300,  # 5 minutes

            # Retry settings
            task_acks_late=True,
            task_reject_on_worker_lost=True,

            # Rate limiting
            worker_concurrency=4,  # Concurrent tasks per worker
        )

        _celery_available = True
        logger.info("[Celery] Celery app configured with dedicated queues: stt, llm, tts, analytics")
        return _celery_app

    except ImportError:
        logger.warning("[Celery] celery package not installed — async workers disabled")
        return None
    except Exception as e:
        logger.warning(f"[Celery] Initialization failed ({e}) — async workers disabled")
        return None


def get_celery_app():
    """Get the Celery app instance."""
    return _celery_app


def is_celery_available() -> bool:
    """Check if Celery is available."""
    return _celery_available


# ============================================================
# Task Definitions
# ============================================================

def _get_openai_client():
    """Get OpenAI client for worker processes."""
    from openai import OpenAI
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def register_tasks(celery_app):
    """Register Celery tasks. Called after celery app is initialized."""
    if not celery_app:
        return

    @celery_app.task(name='workers.transcribe_audio_task', bind=True,
                     max_retries=2, default_retry_delay=5,
                     soft_time_limit=30, time_limit=60)
    def transcribe_audio_task(self, audio_b64: str, language: str = 'en',
                              mime_type: str = 'audio/webm') -> dict:
        """STT Worker: Transcribe audio using Whisper.
        
        Args:
            audio_b64: Base64 encoded audio data
            language: Language code for transcription
            mime_type: MIME type of the audio
            
        Returns:
            Dict with 'text' key containing transcription
        """
        start_time = time.time()
        try:
            client = _get_openai_client()
            audio_bytes = base64.b64decode(audio_b64)

            # Determine file extension
            ext = '.webm'
            mime_ext_map = {
                'audio/webm': '.webm', 'audio/ogg': '.ogg',
                'audio/mp4': '.mp4', 'audio/mpeg': '.mp3',
                'audio/wav': '.wav', 'audio/flac': '.flac',
            }
            ext = mime_ext_map.get(mime_type.lower().strip(), '.webm')

            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            try:
                with open(tmp_path, 'rb') as f:
                    kwargs = {"model": "whisper-1", "file": f}
                    if language and language != 'en':
                        kwargs["language"] = language
                    transcript = client.audio.transcriptions.create(**kwargs)
                
                latency_ms = int((time.time() - start_time) * 1000)
                logger.info(f"[STT Worker] Transcribed {len(audio_bytes)} bytes in {latency_ms}ms")
                
                return {
                    'text': transcript.text,
                    'latency_ms': latency_ms,
                    'audio_size': len(audio_bytes),
                }
            finally:
                os.unlink(tmp_path)

        except Exception as e:
            logger.error(f"[STT Worker] Error: {e}")
            raise self.retry(exc=e)

    @celery_app.task(name='workers.generate_chat_response_task', bind=True,
                     max_retries=2, default_retry_delay=3,
                     soft_time_limit=45, time_limit=90)
    def generate_chat_response_task(self, messages: list, model: str = 'gpt-4o-mini',
                                     max_tokens: int = 300, temperature: float = 0.85) -> dict:
        """LLM Worker: Generate chat response (non-streaming).
        
        For streaming, the main app still handles it directly via Socket.IO.
        This task is for background/batch processing.
        """
        start_time = time.time()
        try:
            client = _get_openai_client()
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            
            text = response.choices[0].message.content
            latency_ms = int((time.time() - start_time) * 1000)
            tokens_used = response.usage.total_tokens if response.usage else 0
            
            logger.info(f"[LLM Worker] Generated {len(text)} chars in {latency_ms}ms, {tokens_used} tokens")
            
            return {
                'text': text,
                'latency_ms': latency_ms,
                'tokens_used': tokens_used,
                'model': model,
            }
        except Exception as e:
            logger.error(f"[LLM Worker] Error: {e}")
            raise self.retry(exc=e)

    @celery_app.task(name='workers.generate_speech_task', bind=True,
                     max_retries=2, default_retry_delay=3,
                     soft_time_limit=30, time_limit=60)
    def generate_speech_task(self, text: str, voice: str = 'coral',
                             instructions: str = '', 
                             response_format: str = 'opus') -> dict:
        """TTS Worker: Generate speech audio.
        
        Args:
            text: Text to convert to speech
            voice: TTS voice name
            instructions: TTS style instructions
            response_format: Audio format
            
        Returns:
            Dict with 'audio_b64' key containing base64 encoded audio
        """
        start_time = time.time()
        try:
            client = _get_openai_client()
            response = client.audio.speech.create(
                model="gpt-4o-mini-tts",
                voice=voice,
                input=text,
                instructions=instructions,
                response_format=response_format,
            )
            
            audio_content = response.content
            audio_b64 = base64.b64encode(audio_content).decode('utf-8')
            latency_ms = int((time.time() - start_time) * 1000)
            
            logger.info(f"[TTS Worker] Generated {len(audio_content)} bytes in {latency_ms}ms")
            
            return {
                'audio_b64': audio_b64,
                'latency_ms': latency_ms,
                'audio_size': len(audio_content),
                'text_length': len(text),
            }
        except Exception as e:
            logger.error(f"[TTS Worker] Error: {e}")
            raise self.retry(exc=e)

    @celery_app.task(name='workers.analyze_conversation_task', bind=True,
                     max_retries=1, default_retry_delay=10,
                     soft_time_limit=60, time_limit=120)
    def analyze_conversation_task(self, conversation_id: str,
                                   messages: list) -> dict:
        """Analytics Worker: Analyze completed conversation for insights.
        
        Runs post-conversation analysis including:
        - Performance assessment (interview mode)
        - Language proficiency estimation (language mode)
        - Issue resolution summary (helpdesk mode)
        """
        start_time = time.time()
        try:
            client = _get_openai_client()

            # Build analysis prompt
            conversation_text = '\n'.join([
                f"{m['role'].capitalize()}: {m['content'][:200]}"
                for m in messages if m['role'] != 'system'
            ][-20:])

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": """Analyze this conversation and provide:
1. A brief performance summary (2-3 sentences)
2. Key strengths demonstrated
3. Areas for improvement
4. Overall score (1-10)
Respond in JSON format with keys: summary, strengths, improvements, score."""},
                    {"role": "user", "content": conversation_text}
                ],
                max_tokens=300,
                temperature=0.3,
            )

            analysis = response.choices[0].message.content
            latency_ms = int((time.time() - start_time) * 1000)

            logger.info(f"[Analytics Worker] Analyzed conversation {conversation_id} in {latency_ms}ms")

            return {
                'conversation_id': conversation_id,
                'analysis': analysis,
                'latency_ms': latency_ms,
            }
        except Exception as e:
            logger.error(f"[Analytics Worker] Error: {e}")
            raise self.retry(exc=e)

    logger.info("[Celery] Tasks registered: transcribe_audio, generate_chat_response, generate_speech, analyze_conversation")
    return {
        'transcribe_audio': transcribe_audio_task,
        'generate_chat_response': generate_chat_response_task,
        'generate_speech': generate_speech_task,
        'analyze_conversation': analyze_conversation_task,
    }


# ============================================================
# Health Check
# ============================================================

def get_celery_health() -> dict:
    """Get Celery worker health status."""
    if not _celery_available or not _celery_app:
        return {'status': 'disabled', 'message': 'Celery not configured'}

    try:
        # Check broker connection
        inspector = _celery_app.control.inspect(timeout=3)
        active = inspector.active()
        registered = inspector.registered()
        stats = inspector.stats()

        if active is None:
            return {'status': 'unhealthy', 'message': 'No workers responding'}

        workers = []
        for worker_name, worker_stats in (stats or {}).items():
            workers.append({
                'name': worker_name,
                'active_tasks': len((active or {}).get(worker_name, [])),
                'registered_tasks': len((registered or {}).get(worker_name, [])),
                'pool_size': worker_stats.get('pool', {}).get('max-concurrency', 0),
            })

        return {
            'status': 'healthy',
            'workers': workers,
            'total_workers': len(workers),
        }
    except Exception as e:
        return {'status': 'unhealthy', 'message': str(e)}
