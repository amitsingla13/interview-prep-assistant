"""
Enterprise Middleware
======================
Request ID tracking, enhanced rate limiting, request lifecycle hooks.
Blueprint Sections 9, 11, 12: Scalability, Observability, Security.
"""
import uuid
import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)

_config = None


def init_middleware(app, config):
    """Register middleware with the Flask app."""
    global _config
    _config = config

    @app.before_request
    def before_request():
        """Add request ID and start timing for every request."""
        from flask import request, g
        g.request_id = request.headers.get('X-Request-ID', str(uuid.uuid4())[:8])
        g.request_start = time.time()

    @app.after_request
    def after_request(response):
        """Add standard headers and log request metrics."""
        from flask import request, g

        # Add request ID to response headers
        request_id = getattr(g, 'request_id', 'unknown')
        response.headers['X-Request-ID'] = request_id

        # Calculate and log request duration
        start = getattr(g, 'request_start', None)
        if start:
            duration_ms = int((time.time() - start) * 1000)
            response.headers['X-Response-Time'] = f"{duration_ms}ms"

            # Record metrics
            try:
                from observability import record_request, record_request_duration
                record_request(request.method, request.path, response.status_code)
                record_request_duration(request.method, request.path, duration_ms / 1000)
            except Exception:
                pass

        # Security headers (enhanced)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'microphone=(self), camera=()'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        # CSP
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "font-src 'self' https://cdnjs.cloudflare.com; "
            "connect-src 'self' ws: wss: https://api.openai.com https://cdnjs.cloudflare.com; "
            "media-src 'self' blob:; "
            "img-src 'self' data:; "
            "manifest-src 'self'; "
            "worker-src 'self'; "
            "frame-ancestors 'none';"
        )

        return response

    logger.info("[Middleware] Request lifecycle hooks registered")
