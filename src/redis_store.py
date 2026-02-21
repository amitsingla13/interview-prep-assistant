"""
Redis Session Store
====================
Redis-backed session store for conversation state with graceful fallback to in-memory dict.
Supports TTL-based expiration, atomic operations, and multi-instance deployment.

Blueprint Section 8: State Management — Redis for ephemeral session state.
"""
import json
import time
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# In-memory fallback store
_memory_store: Dict[str, Dict] = {}
_redis_client = None
_redis_available = False
_config = None


def init_redis(config):
    """Initialize Redis connection. Falls back to in-memory if Redis is unavailable."""
    global _redis_client, _redis_available, _config
    _config = config

    if not config.REDIS_ENABLED:
        logger.info("[Redis] REDIS_URL not configured — using in-memory session store")
        return False

    try:
        import redis
        _redis_client = redis.Redis.from_url(
            config.REDIS_URL,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
        )
        # Test connection
        _redis_client.ping()
        _redis_available = True
        logger.info(f"[Redis] Connected to Redis at {config.REDIS_URL.split('@')[-1] if '@' in config.REDIS_URL else config.REDIS_URL}")
        return True
    except ImportError:
        logger.warning("[Redis] redis-py not installed — using in-memory session store")
        return False
    except Exception as e:
        logger.warning(f"[Redis] Connection failed ({e}) — using in-memory session store")
        _redis_available = False
        return False


def _key(sid: str) -> str:
    """Generate Redis key with prefix."""
    prefix = _config.REDIS_PREFIX if _config else 'ivprep:'
    return f"{prefix}session:{sid}"


def _ttl() -> int:
    """Get session TTL from config."""
    return _config.REDIS_SESSION_TTL if _config else 7200


# ============================================================
# Core Session Operations
# ============================================================

def get_session(sid: str) -> Optional[Dict[str, Any]]:
    """Get session data. Returns None if not found."""
    if _redis_available:
        try:
            data = _redis_client.get(_key(sid))
            if data:
                session = json.loads(data)
                session['last_activity'] = time.time()
                # Refresh TTL on access
                _redis_client.expire(_key(sid), _ttl())
                return session
            return None
        except Exception as e:
            logger.error(f"[Redis] get_session error: {e}")
            # Fallback to memory
            return _memory_store.get(sid)
    else:
        return _memory_store.get(sid)


def set_session(sid: str, session_data: Dict[str, Any]):
    """Store session data."""
    session_data['last_activity'] = time.time()
    if _redis_available:
        try:
            _redis_client.setex(
                _key(sid),
                _ttl(),
                json.dumps(session_data, default=str)
            )
        except Exception as e:
            logger.error(f"[Redis] set_session error: {e}")
            _memory_store[sid] = session_data
    else:
        _memory_store[sid] = session_data


def delete_session(sid: str):
    """Delete a session."""
    if _redis_available:
        try:
            _redis_client.delete(_key(sid))
        except Exception as e:
            logger.error(f"[Redis] delete_session error: {e}")
    _memory_store.pop(sid, None)


def session_exists(sid: str) -> bool:
    """Check if session exists."""
    if _redis_available:
        try:
            return _redis_client.exists(_key(sid)) > 0
        except Exception:
            return sid in _memory_store
    return sid in _memory_store


def get_or_create_session(sid: str, defaults: Optional[Dict] = None) -> Dict[str, Any]:
    """Get existing session or create new one with defaults."""
    session = get_session(sid)
    if session is None:
        session = defaults or {
            'messages': [],
            'mode': None,
            'language': 'en',
            'last_activity': time.time(),
            'exchange_count': 0,
            'voice_mode': False,
            'session_start': time.time(),
            'emotional_tone': 'neutral',
            'last_assistant_partial': '',
        }
        set_session(sid, session)
    return session


def update_session_field(sid: str, field: str, value: Any):
    """Update a single field in a session."""
    session = get_session(sid)
    if session:
        session[field] = value
        set_session(sid, session)


def append_message(sid: str, message: Dict[str, str]):
    """Append a message to session history."""
    session = get_session(sid)
    if session:
        session['messages'].append(message)
        set_session(sid, session)


# ============================================================
# Session Management
# ============================================================

def get_session_count() -> int:
    """Get current number of active sessions."""
    if _redis_available:
        try:
            prefix = _config.REDIS_PREFIX if _config else 'ivprep:'
            keys = _redis_client.keys(f"{prefix}session:*")
            return len(keys)
        except Exception:
            return len(_memory_store)
    return len(_memory_store)


def cleanup_stale_sessions(timeout: int = 3600):
    """Remove sessions older than timeout."""
    if _redis_available:
        # Redis handles TTL-based expiration automatically
        return 0

    now = time.time()
    stale = [sid for sid, conv in _memory_store.items()
             if now - conv.get('last_activity', 0) > timeout]
    for sid in stale:
        _memory_store.pop(sid, None)
    return len(stale)


def get_all_session_ids() -> list:
    """Get all active session IDs."""
    if _redis_available:
        try:
            prefix = _config.REDIS_PREFIX if _config else 'ivprep:'
            keys = _redis_client.keys(f"{prefix}session:*")
            return [k.replace(f"{prefix}session:", '') for k in keys]
        except Exception:
            return list(_memory_store.keys())
    return list(_memory_store.keys())


# ============================================================
# TTS Cache (Redis-backed)
# ============================================================

_tts_cache_memory: Dict[str, Dict] = {}
_tts_cache_hits = 0
_tts_cache_misses = 0


def get_tts_cache(key: str) -> Optional[str]:
    """Get TTS audio from cache. Returns base64 string or None."""
    global _tts_cache_hits
    if _redis_available and _config and _config.TTS_CACHE_BACKEND == 'redis':
        try:
            prefix = _config.REDIS_PREFIX if _config else 'ivprep:'
            data = _redis_client.get(f"{prefix}tts:{key}")
            if data:
                _tts_cache_hits += 1
                _redis_client.expire(f"{prefix}tts:{key}", 3600)  # Refresh 1hr TTL
                return data
        except Exception as e:
            logger.error(f"[Redis] TTS cache get error: {e}")

    # Memory fallback
    if key in _tts_cache_memory:
        _tts_cache_memory[key]['last_used'] = time.time()
        _tts_cache_hits += 1
        return _tts_cache_memory[key]['audio_b64']
    return None


def set_tts_cache(key: str, audio_b64: str, max_size: int = 200):
    """Store TTS audio in cache."""
    global _tts_cache_misses
    _tts_cache_misses += 1

    if _redis_available and _config and _config.TTS_CACHE_BACKEND == 'redis':
        try:
            prefix = _config.REDIS_PREFIX if _config else 'ivprep:'
            _redis_client.setex(f"{prefix}tts:{key}", 3600, audio_b64)
            return
        except Exception as e:
            logger.error(f"[Redis] TTS cache set error: {e}")

    # Memory fallback
    if len(_tts_cache_memory) >= max_size:
        oldest_key = min(_tts_cache_memory, key=lambda k: _tts_cache_memory[k]['last_used'])
        del _tts_cache_memory[oldest_key]

    _tts_cache_memory[key] = {
        'audio_b64': audio_b64,
        'last_used': time.time(),
        'size': len(audio_b64)
    }


def get_tts_cache_stats() -> Dict:
    """Get TTS cache statistics."""
    return {
        'hits': _tts_cache_hits,
        'misses': _tts_cache_misses,
        'hit_rate': round(_tts_cache_hits / max(1, _tts_cache_hits + _tts_cache_misses) * 100, 1),
        'size': len(_tts_cache_memory),
        'backend': 'redis' if (_redis_available and _config and _config.TTS_CACHE_BACKEND == 'redis') else 'memory',
    }


# ============================================================
# Rate Limiting (Redis-backed token bucket)
# ============================================================

_rate_limit_memory: Dict[str, Dict] = {}


def check_rate_limit(sid: str, rpm: int = 15, rph: int = 200) -> bool:
    """Token bucket rate limiting. Returns True if allowed."""
    if _redis_available:
        try:
            return _check_rate_limit_redis(sid, rpm, rph)
        except Exception as e:
            logger.error(f"[Redis] Rate limit error: {e}")

    return _check_rate_limit_memory(sid, rpm, rph)


def _check_rate_limit_redis(sid: str, rpm: int, rph: int) -> bool:
    """Redis-based sliding window rate limiting."""
    prefix = _config.REDIS_PREFIX if _config else 'ivprep:'
    now = time.time()
    pipe = _redis_client.pipeline()

    minute_key = f"{prefix}rl:m:{sid}"
    hour_key = f"{prefix}rl:h:{sid}"

    # Remove old entries (sliding window)
    pipe.zremrangebyscore(minute_key, 0, now - 60)
    pipe.zremrangebyscore(hour_key, 0, now - 3600)

    # Count entries
    pipe.zcard(minute_key)
    pipe.zcard(hour_key)

    results = pipe.execute()
    minute_count = results[2]
    hour_count = results[3]

    if minute_count >= rpm or hour_count >= rph:
        return False

    # Add current request
    pipe2 = _redis_client.pipeline()
    pipe2.zadd(minute_key, {str(now): now})
    pipe2.zadd(hour_key, {str(now): now})
    pipe2.expire(minute_key, 60)
    pipe2.expire(hour_key, 3600)
    pipe2.execute()

    return True


def _check_rate_limit_memory(sid: str, rpm: int, rph: int) -> bool:
    """In-memory sliding window rate limiting."""
    now = time.time()
    if sid not in _rate_limit_memory:
        _rate_limit_memory[sid] = {'timestamps': []}

    tracker = _rate_limit_memory[sid]
    tracker['timestamps'] = [t for t in tracker['timestamps'] if now - t < 3600]

    recent_minute = [t for t in tracker['timestamps'] if now - t < 60]
    if len(recent_minute) >= rpm:
        return False
    if len(tracker['timestamps']) >= rph:
        return False

    tracker['timestamps'].append(now)
    return True


def clear_rate_limit(sid: str):
    """Clear rate limit data for a session."""
    if _redis_available:
        try:
            prefix = _config.REDIS_PREFIX if _config else 'ivprep:'
            _redis_client.delete(f"{prefix}rl:m:{sid}", f"{prefix}rl:h:{sid}")
        except Exception:
            pass
    _rate_limit_memory.pop(sid, None)


# ============================================================
# Health Check
# ============================================================

def get_redis_health() -> Dict:
    """Get Redis health status for health check endpoint."""
    if not _config or not _config.REDIS_ENABLED:
        return {'status': 'disabled', 'message': 'REDIS_URL not configured'}

    if not _redis_available:
        return {'status': 'unhealthy', 'message': 'Redis connection failed'}

    try:
        info = _redis_client.info('server')
        return {
            'status': 'healthy',
            'version': info.get('redis_version', 'unknown'),
            'connected_clients': _redis_client.info('clients').get('connected_clients', 0),
            'used_memory_human': _redis_client.info('memory').get('used_memory_human', 'unknown'),
        }
    except Exception as e:
        return {'status': 'unhealthy', 'message': str(e)}
