"""
Enterprise Configuration Management
=====================================
Centralized configuration with environment-based profiles (dev/staging/prod).
All settings loaded from environment variables with sensible defaults.
Supports graceful degradation when optional services (Redis, Postgres, Celery) aren't available.
"""
import os
import hashlib
import logging

logger = logging.getLogger(__name__)


class BaseConfig:
    """Base configuration — shared across all environments."""

    # --- App ---
    APP_NAME = "Interview Preparation Assistant"
    APP_VERSION = "2.0.0"

    # --- Secret Key ---
    SECRET_KEY = os.getenv('SECRET_KEY') or hashlib.sha256(os.urandom(32)).hexdigest()

    # --- CORS ---
    ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', '*')

    # --- OpenAI ---
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    OPENAI_CHAT_MODEL = os.getenv('OPENAI_CHAT_MODEL', 'gpt-4o-mini')
    OPENAI_TTS_MODEL = os.getenv('OPENAI_TTS_MODEL', 'gpt-4o-mini-tts')
    OPENAI_STT_MODEL = os.getenv('OPENAI_STT_MODEL', 'whisper-1')
    OPENAI_REALTIME_MODEL = os.getenv('OPENAI_REALTIME_MODEL', 'gpt-realtime')

    # --- Redis ---
    REDIS_URL = os.getenv('REDIS_URL', '')  # e.g., redis://localhost:6379/0
    REDIS_ENABLED = bool(os.getenv('REDIS_URL', ''))
    REDIS_PREFIX = os.getenv('REDIS_PREFIX', 'ivprep:')
    REDIS_SESSION_TTL = int(os.getenv('REDIS_SESSION_TTL', '7200'))  # 2 hours

    # --- PostgreSQL ---
    DATABASE_URL = os.getenv('DATABASE_URL', '')  # e.g., postgresql://user:pass@host/db
    DATABASE_ENABLED = bool(os.getenv('DATABASE_URL', ''))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': int(os.getenv('DB_POOL_SIZE', '5')),
        'max_overflow': int(os.getenv('DB_MAX_OVERFLOW', '10')),
        'pool_timeout': int(os.getenv('DB_POOL_TIMEOUT', '30')),
        'pool_recycle': int(os.getenv('DB_POOL_RECYCLE', '1800')),
        'pool_pre_ping': True,
    }

    # --- Celery ---
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', os.getenv('REDIS_URL', ''))
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', os.getenv('REDIS_URL', ''))
    CELERY_ENABLED = bool(os.getenv('CELERY_BROKER_URL', '') or os.getenv('REDIS_URL', ''))

    # --- JWT Authentication ---
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', '3600'))  # 1 hour
    JWT_REFRESH_TOKEN_EXPIRES = int(os.getenv('JWT_REFRESH_TOKEN_EXPIRES', '604800'))  # 7 days
    JWT_ALGORITHM = 'HS256'
    AUTH_ENABLED = os.getenv('AUTH_ENABLED', 'false').lower() == 'true'

    # --- Rate Limiting ---
    RATE_LIMIT_REQUESTS_PER_MINUTE = int(os.getenv('RATE_LIMIT_RPM', '15'))
    RATE_LIMIT_REQUESTS_PER_HOUR = int(os.getenv('RATE_LIMIT_RPH', '200'))
    RATE_LIMIT_STRATEGY = os.getenv('RATE_LIMIT_STRATEGY', 'token_bucket')  # token_bucket or sliding_window

    # --- Session & Security ---
    MAX_SESSIONS = int(os.getenv('MAX_SESSIONS', '200'))
    MAX_TEXT_LENGTH = int(os.getenv('MAX_TEXT_LENGTH', '2000'))
    MAX_AUDIO_SIZE = int(os.getenv('MAX_AUDIO_SIZE', str(3 * 1024 * 1024)))  # 3MB
    SESSION_TIMEOUT = int(os.getenv('SESSION_TIMEOUT', '3600'))  # 1 hour
    SOCKET_MAX_BUFFER = int(os.getenv('SOCKET_MAX_BUFFER', str(5 * 1024 * 1024)))  # 5MB

    # --- TTS Cache ---
    TTS_CACHE_MAX_SIZE = int(os.getenv('TTS_CACHE_MAX_SIZE', '200'))
    TTS_CACHE_BACKEND = os.getenv('TTS_CACHE_BACKEND', 'memory')  # memory or redis

    # --- Observability ---
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FORMAT = os.getenv('LOG_FORMAT', 'json')  # json or text
    OTEL_ENABLED = os.getenv('OTEL_ENABLED', 'false').lower() == 'true'
    OTEL_SERVICE_NAME = os.getenv('OTEL_SERVICE_NAME', 'interview-prep-assistant')
    OTEL_EXPORTER_ENDPOINT = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'http://localhost:4317')
    PROMETHEUS_ENABLED = os.getenv('PROMETHEUS_ENABLED', 'false').lower() == 'true'
    PROMETHEUS_PORT = int(os.getenv('PROMETHEUS_PORT', '9090'))

    # --- Voice AI Pipeline ---
    TTS_VOICES = {
        'interview': os.getenv('TTS_VOICE_INTERVIEW', 'marin'),
        'language': os.getenv('TTS_VOICE_LANGUAGE', 'cedar'),
        'helpdesk': os.getenv('TTS_VOICE_HELPDESK', 'cedar'),
    }
    STREAMING_FIRST_CHUNK_SENTENCES = int(os.getenv('STREAMING_FIRST_CHUNK_SENTENCES', '1'))
    STREAMING_SUBSEQUENT_CHUNK_SENTENCES = int(os.getenv('STREAMING_SUBSEQUENT_CHUNK_SENTENCES', '2'))
    LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', '0.85'))
    LLM_MAX_TOKENS_INTERVIEW = int(os.getenv('LLM_MAX_TOKENS_INTERVIEW', '300'))
    LLM_MAX_TOKENS_LANGUAGE = int(os.getenv('LLM_MAX_TOKENS_LANGUAGE', '200'))
    LLM_MAX_TOKENS_HELPDESK = int(os.getenv('LLM_MAX_TOKENS_HELPDESK', '350'))
    MEMORY_COMPRESSION_THRESHOLD = int(os.getenv('MEMORY_COMPRESSION_THRESHOLD', '21'))

    # --- Frontend VAD defaults (sent to client) ---
    VAD_SILENCE_THRESHOLD = int(os.getenv('VAD_SILENCE_THRESHOLD', '15'))
    VAD_SILENCE_DURATION_MS = int(os.getenv('VAD_SILENCE_DURATION_MS', '1500'))
    VAD_CHECK_INTERVAL_MS = int(os.getenv('VAD_CHECK_INTERVAL_MS', '50'))
    VAD_INTERRUPT_THRESHOLD = int(os.getenv('VAD_INTERRUPT_THRESHOLD', '22'))
    VAD_INTERRUPT_SPEECH_MIN_MS = int(os.getenv('VAD_INTERRUPT_SPEECH_MIN_MS', '200'))
    VAD_ADAPTIVE_ENABLED = os.getenv('VAD_ADAPTIVE_ENABLED', 'true').lower() == 'true'
    VAD_CALIBRATION_DURATION_MS = int(os.getenv('VAD_CALIBRATION_DURATION_MS', '2000'))

    @classmethod
    def get_allowed_origins(cls):
        """Parse ALLOWED_ORIGINS into list or '*'."""
        origins = cls.ALLOWED_ORIGINS
        if origins != '*':
            return [o.strip() for o in origins.split(',')]
        return origins

    @classmethod
    def get_sqlalchemy_uri(cls):
        """Fix Render's postgres:// URL to postgresql://."""
        url = cls.DATABASE_URL
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        return url

    @classmethod
    def validate(cls):
        """Validate critical configuration on startup."""
        warnings = []
        errors = []

        if not cls.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY is required")

        if cls.SECRET_KEY == hashlib.sha256(os.urandom(32)).hexdigest():
            warnings.append("No SECRET_KEY set — generated random key (will change on restart)")

        if cls.ALLOWED_ORIGINS == '*':
            warnings.append("ALLOWED_ORIGINS='*' — restrict to your domain in production")

        if not cls.REDIS_ENABLED:
            warnings.append("REDIS_URL not set — using in-memory session store (not suitable for multi-instance)")

        if not cls.DATABASE_ENABLED:
            warnings.append("DATABASE_URL not set — conversation history will not be persisted")

        if not cls.AUTH_ENABLED:
            warnings.append("AUTH_ENABLED=false — no JWT authentication (open access)")

        for w in warnings:
            logger.warning(f"[Config] {w}")
        for e in errors:
            logger.error(f"[Config] {e}")

        return len(errors) == 0


class DevelopmentConfig(BaseConfig):
    """Development environment settings."""
    DEBUG = True
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG')
    LOG_FORMAT = os.getenv('LOG_FORMAT', 'text')
    RATE_LIMIT_REQUESTS_PER_MINUTE = int(os.getenv('RATE_LIMIT_RPM', '60'))
    RATE_LIMIT_REQUESTS_PER_HOUR = int(os.getenv('RATE_LIMIT_RPH', '1000'))


class StagingConfig(BaseConfig):
    """Staging environment settings."""
    DEBUG = False
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')


class ProductionConfig(BaseConfig):
    """Production environment settings."""
    DEBUG = False
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'WARNING')
    LOG_FORMAT = 'json'
    # Enforce stricter settings in production
    MAX_SESSIONS = int(os.getenv('MAX_SESSIONS', '500'))
    RATE_LIMIT_REQUESTS_PER_MINUTE = int(os.getenv('RATE_LIMIT_RPM', '10'))


# Config selector
CONFIG_MAP = {
    'development': DevelopmentConfig,
    'staging': StagingConfig,
    'production': ProductionConfig,
}


def get_config():
    """Get the config class for the current environment."""
    env = os.getenv('FLASK_ENV', 'development').lower()
    config_cls = CONFIG_MAP.get(env, DevelopmentConfig)
    logger.info(f"[Config] Using {env} configuration ({config_cls.__name__})")
    return config_cls
