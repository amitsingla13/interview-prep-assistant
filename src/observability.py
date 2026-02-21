"""
OpenTelemetry Observability
============================
Distributed tracing, Prometheus metrics, and structured JSON logging.
Blueprint Section 11: Observability — OpenTelemetry, metrics, distributed traces.

Gracefully disabled when OTEL_ENABLED=false (default).
"""
import os
import time
import json
import logging
import sys
from typing import Optional, Dict, Any
from functools import wraps
from contextlib import contextmanager

logger = logging.getLogger(__name__)

_config = None
_tracer = None
_meter = None
_metrics = {}
_otel_available = False


# ============================================================
# Structured JSON Logging
# ============================================================

class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for production environments."""

    def format(self, record):
        log_entry = {
            'timestamp': self.formatTime(record, self.datefmt),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        if hasattr(record, 'session_id'):
            log_entry['session_id'] = record.session_id
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'trace_id'):
            log_entry['trace_id'] = record.trace_id
        if hasattr(record, 'span_id'):
            log_entry['span_id'] = record.span_id
        if hasattr(record, 'latency_ms'):
            log_entry['latency_ms'] = record.latency_ms
        if hasattr(record, 'extra_data'):
            log_entry['data'] = record.extra_data

        return json.dumps(log_entry, default=str)


def setup_logging(config):
    """Configure logging based on environment settings."""
    global _config
    _config = config

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.LOG_LEVEL.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)

    if config.LOG_FORMAT == 'json':
        handler.setFormatter(JSONFormatter(datefmt='%Y-%m-%dT%H:%M:%S'))
    else:
        handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))

    root_logger.addHandler(handler)

    # Suppress noisy third-party loggers
    logging.getLogger('engineio').setLevel(logging.WARNING)
    logging.getLogger('socketio').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

    logger.info(f"[Observability] Logging configured: level={config.LOG_LEVEL}, format={config.LOG_FORMAT}")


# ============================================================
# OpenTelemetry Tracing
# ============================================================

def init_tracing(config):
    """Initialize OpenTelemetry distributed tracing."""
    global _tracer, _otel_available, _config
    _config = config

    if not config.OTEL_ENABLED:
        logger.info("[Observability] OpenTelemetry tracing DISABLED")
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.semconv.resource import ResourceAttributes

        resource = Resource.create({
            ResourceAttributes.SERVICE_NAME: config.OTEL_SERVICE_NAME,
            ResourceAttributes.SERVICE_VERSION: config.APP_VERSION,
            ResourceAttributes.DEPLOYMENT_ENVIRONMENT: os.getenv('FLASK_ENV', 'development'),
        })

        provider = TracerProvider(resource=resource)

        # Try to set up OTLP exporter
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            otlp_exporter = OTLPSpanExporter(endpoint=config.OTEL_EXPORTER_ENDPOINT)
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info(f"[Observability] OTLP exporter configured: {config.OTEL_EXPORTER_ENDPOINT}")
        except ImportError:
            # Fallback to console exporter for development
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
            logger.info("[Observability] Using console span exporter (install opentelemetry-exporter-otlp for OTLP)")

        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(config.OTEL_SERVICE_NAME)
        _otel_available = True

        # Instrument Flask
        try:
            from opentelemetry.instrumentation.flask import FlaskInstrumentor
            logger.info("[Observability] Flask instrumentation available")
        except ImportError:
            pass

        logger.info("[Observability] OpenTelemetry tracing ENABLED")
        return True

    except ImportError:
        logger.warning("[Observability] opentelemetry-sdk not installed — tracing disabled")
        return False
    except Exception as e:
        logger.warning(f"[Observability] Tracing init failed ({e}) — disabled")
        return False


def instrument_flask_app(app):
    """Instrument Flask app with OpenTelemetry (if available)."""
    if not _otel_available:
        return
    try:
        from opentelemetry.instrumentation.flask import FlaskInstrumentor
        FlaskInstrumentor().instrument_app(app)
        logger.info("[Observability] Flask app instrumented with OpenTelemetry")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"[Observability] Flask instrumentation failed: {e}")


# ============================================================
# Prometheus Metrics
# ============================================================

# In-memory metrics counters (works without Prometheus client library)
_counters = {}
_histograms = {}
_gauges = {}


def init_metrics(config):
    """Initialize Prometheus metrics."""
    global _metrics, _config
    _config = config

    if not config.PROMETHEUS_ENABLED:
        logger.info("[Observability] Prometheus metrics DISABLED")
        return False

    try:
        from prometheus_client import Counter, Histogram, Gauge, start_http_server, REGISTRY

        _metrics = {
            # Request metrics
            'requests_total': Counter(
                'voice_ai_requests_total',
                'Total requests processed',
                ['method', 'endpoint', 'status']
            ),
            'request_duration': Histogram(
                'voice_ai_request_duration_seconds',
                'Request duration in seconds',
                ['method', 'endpoint'],
                buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
            ),

            # Voice AI pipeline metrics
            'stt_duration': Histogram(
                'voice_ai_stt_duration_seconds',
                'STT transcription duration',
                ['language'],
                buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
            ),
            'llm_duration': Histogram(
                'voice_ai_llm_duration_seconds',
                'LLM response generation duration',
                ['model', 'mode'],
                buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0]
            ),
            'tts_duration': Histogram(
                'voice_ai_tts_duration_seconds',
                'TTS speech generation duration',
                ['voice', 'mode'],
                buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
            ),
            'time_to_first_audio': Histogram(
                'voice_ai_time_to_first_audio_seconds',
                'Time from user message to first audio chunk',
                ['mode'],
                buckets=[0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0]
            ),

            # Session metrics
            'active_sessions': Gauge(
                'voice_ai_active_sessions',
                'Number of active sessions'
            ),
            'active_streams': Gauge(
                'voice_ai_active_streams',
                'Number of active streaming responses'
            ),

            # Error metrics
            'errors_total': Counter(
                'voice_ai_errors_total',
                'Total errors',
                ['component', 'error_type']
            ),

            # Cost metrics
            'tokens_used': Counter(
                'voice_ai_tokens_used_total',
                'Total tokens consumed',
                ['model', 'type']
            ),
            'tts_cache_hits': Counter(
                'voice_ai_tts_cache_hits_total',
                'TTS cache hits'
            ),
            'tts_cache_misses': Counter(
                'voice_ai_tts_cache_misses_total',
                'TTS cache misses'
            ),

            # Interruption metrics
            'interruptions_total': Counter(
                'voice_ai_interruptions_total',
                'Total user interruptions',
                ['mode']
            ),

            # Rate limiting
            'rate_limited': Counter(
                'voice_ai_rate_limited_total',
                'Total rate-limited requests'
            ),
        }

        # Start Prometheus HTTP server on separate port
        try:
            start_http_server(config.PROMETHEUS_PORT)
            logger.info(f"[Observability] Prometheus metrics server started on port {config.PROMETHEUS_PORT}")
        except OSError:
            logger.warning(f"[Observability] Prometheus port {config.PROMETHEUS_PORT} already in use")

        logger.info("[Observability] Prometheus metrics ENABLED")
        return True

    except ImportError:
        logger.warning("[Observability] prometheus_client not installed — using in-memory counters")
        # Use simple in-memory counters as fallback
        return False
    except Exception as e:
        logger.warning(f"[Observability] Metrics init failed ({e})")
        return False


# ============================================================
# Metric Recording Functions (safe to call even when disabled)
# ============================================================

def record_request(method: str, endpoint: str, status: int):
    """Record an HTTP request metric."""
    if 'requests_total' in _metrics:
        _metrics['requests_total'].labels(method=method, endpoint=endpoint, status=str(status)).inc()
    _counters.setdefault('requests_total', 0)
    _counters['requests_total'] += 1


def record_request_duration(method: str, endpoint: str, duration_seconds: float):
    """Record request duration."""
    if 'request_duration' in _metrics:
        _metrics['request_duration'].labels(method=method, endpoint=endpoint).observe(duration_seconds)


def record_stt_duration(language: str, duration_seconds: float):
    """Record STT transcription duration."""
    if 'stt_duration' in _metrics:
        _metrics['stt_duration'].labels(language=language).observe(duration_seconds)
    _histograms.setdefault('stt_latency_ms', []).append(duration_seconds * 1000)


def record_llm_duration(model: str, mode: str, duration_seconds: float):
    """Record LLM generation duration."""
    if 'llm_duration' in _metrics:
        _metrics['llm_duration'].labels(model=model, mode=mode).observe(duration_seconds)
    _histograms.setdefault('llm_latency_ms', []).append(duration_seconds * 1000)


def record_tts_duration(voice: str, mode: str, duration_seconds: float):
    """Record TTS generation duration."""
    if 'tts_duration' in _metrics:
        _metrics['tts_duration'].labels(voice=voice, mode=mode).observe(duration_seconds)
    _histograms.setdefault('tts_latency_ms', []).append(duration_seconds * 1000)


def record_time_to_first_audio(mode: str, duration_seconds: float):
    """Record time to first audio chunk."""
    if 'time_to_first_audio' in _metrics:
        _metrics['time_to_first_audio'].labels(mode=mode).observe(duration_seconds)
    _histograms.setdefault('ttfa_ms', []).append(duration_seconds * 1000)


def record_error(component: str, error_type: str):
    """Record an error."""
    if 'errors_total' in _metrics:
        _metrics['errors_total'].labels(component=component, error_type=error_type).inc()
    _counters.setdefault('errors_total', 0)
    _counters['errors_total'] += 1


def record_tokens(model: str, token_type: str, count: int):
    """Record token usage."""
    if 'tokens_used' in _metrics:
        _metrics['tokens_used'].labels(model=model, type=token_type).inc(count)
    _counters.setdefault('tokens_total', 0)
    _counters['tokens_total'] += count


def record_tts_cache_hit():
    """Record TTS cache hit."""
    if 'tts_cache_hits' in _metrics:
        _metrics['tts_cache_hits'].inc()


def record_tts_cache_miss():
    """Record TTS cache miss."""
    if 'tts_cache_misses' in _metrics:
        _metrics['tts_cache_misses'].inc()


def record_interruption(mode: str):
    """Record user interruption."""
    if 'interruptions_total' in _metrics:
        _metrics['interruptions_total'].labels(mode=mode).inc()
    _counters.setdefault('interruptions', 0)
    _counters['interruptions'] += 1


def record_rate_limited():
    """Record a rate-limited request."""
    if 'rate_limited' in _metrics:
        _metrics['rate_limited'].inc()
    _counters.setdefault('rate_limited', 0)
    _counters['rate_limited'] += 1


def set_active_sessions(count: int):
    """Set current active session count."""
    if 'active_sessions' in _metrics:
        _metrics['active_sessions'].set(count)
    _gauges['active_sessions'] = count


def set_active_streams(count: int):
    """Set current active streaming count."""
    if 'active_streams' in _metrics:
        _metrics['active_streams'].set(count)
    _gauges['active_streams'] = count


# ============================================================
# Tracing Helpers
# ============================================================

@contextmanager
def trace_span(name: str, attributes: Dict[str, Any] = None):
    """Create a trace span context manager. No-op if tracing is disabled."""
    if _tracer and _otel_available:
        from opentelemetry import trace
        with _tracer.start_as_current_span(name) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, str(value))
            try:
                yield span
            except Exception as e:
                span.set_attribute('error', True)
                span.set_attribute('error.message', str(e))
                raise
    else:
        yield None


def trace_function(name: str = None):
    """Decorator to trace a function call."""
    def decorator(f):
        span_name = name or f"{f.__module__}.{f.__name__}"
        @wraps(f)
        def wrapper(*args, **kwargs):
            with trace_span(span_name):
                return f(*args, **kwargs)
        return wrapper
    return decorator


# ============================================================
# Metrics Summary (for health check endpoint)
# ============================================================

def get_metrics_summary() -> Dict:
    """Get a summary of current metrics for the health check endpoint."""
    summary = {
        'otel_tracing': 'enabled' if _otel_available else 'disabled',
        'prometheus': 'enabled' if _metrics else 'disabled (in-memory counters)',
    }

    # Add in-memory counter stats
    if _counters:
        summary['counters'] = dict(_counters)

    if _gauges:
        summary['gauges'] = dict(_gauges)

    # Add histogram summaries (last N values)
    if _histograms:
        for name, values in _histograms.items():
            recent = values[-100:]  # Last 100 values
            if recent:
                summary[f'{name}_avg'] = round(sum(recent) / len(recent), 1)
                summary[f'{name}_p95'] = round(sorted(recent)[int(len(recent) * 0.95)], 1)
                summary[f'{name}_count'] = len(values)

    return summary


def get_latency_budget() -> Dict:
    """Get latency budget vs actual performance.
    Blueprint Section 10: Latency Budget."""
    budget = {
        'target_total_ms': 2000,
        'budget': {
            'stt_ms': 500,
            'llm_first_token_ms': 300,
            'tts_first_chunk_ms': 400,
            'network_overhead_ms': 200,
        },
    }

    # Add actual measurements
    for metric_name, budget_key in [
        ('stt_latency_ms', 'actual_stt_ms'),
        ('llm_latency_ms', 'actual_llm_ms'),
        ('tts_latency_ms', 'actual_tts_ms'),
        ('ttfa_ms', 'actual_ttfa_ms'),
    ]:
        values = _histograms.get(metric_name, [])
        if values:
            recent = values[-50:]
            budget[budget_key] = round(sum(recent) / len(recent), 1)

    return budget
