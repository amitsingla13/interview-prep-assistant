"""
JWT Authentication Module
==========================
Token-based authentication with register/login/refresh endpoints.
Blueprint Section 12: Security — JWT auth replacing plain Socket.IO sessions.

Gracefully disabled when AUTH_ENABLED=false (default for development).
"""
import time
import hashlib
import hmac
import json
import base64
import logging
import re
from datetime import datetime, timezone
from functools import wraps
from typing import Optional, Dict, Tuple

logger = logging.getLogger(__name__)

_config = None
_db_module = None


def init_auth(config, database_module=None):
    """Initialize auth module with config and optional database module."""
    global _config, _db_module
    _config = config
    _db_module = database_module

    if config.AUTH_ENABLED:
        logger.info("[Auth] JWT authentication ENABLED")
    else:
        logger.info("[Auth] JWT authentication DISABLED (open access)")


# ============================================================
# Password Hashing (using hashlib — no bcrypt dependency needed)
# ============================================================

def hash_password(password: str) -> str:
    """Hash password using PBKDF2-SHA256."""
    salt = hashlib.sha256((_config.JWT_SECRET_KEY if _config else 'salt').encode()).hexdigest()[:16]
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"pbkdf2:sha256:{salt}:{key.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash."""
    try:
        parts = password_hash.split(':')
        if len(parts) != 4:
            return False
        _, _, salt, expected_hex = parts
        key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return hmac.compare_digest(key.hex(), expected_hex)
    except Exception:
        return False


# ============================================================
# JWT Token Creation & Verification (pure Python — no PyJWT needed)
# ============================================================

def _b64url_encode(data: bytes) -> str:
    """Base64url encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _b64url_decode(s: str) -> bytes:
    """Base64url decode with padding."""
    s += '=' * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(s)


def create_token(payload: Dict, expires_in: int = 3600) -> str:
    """Create a JWT token."""
    secret = _config.JWT_SECRET_KEY if _config else 'secret'
    
    header = {'alg': 'HS256', 'typ': 'JWT'}
    
    now = int(time.time())
    payload = {
        **payload,
        'iat': now,
        'exp': now + expires_in,
    }
    
    header_b64 = _b64url_encode(json.dumps(header).encode())
    payload_b64 = _b64url_encode(json.dumps(payload).encode())
    
    signing_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    sig_b64 = _b64url_encode(signature)
    
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def verify_token(token: str) -> Tuple[bool, Optional[Dict]]:
    """Verify a JWT token. Returns (valid, payload)."""
    try:
        secret = _config.JWT_SECRET_KEY if _config else 'secret'
        
        parts = token.split('.')
        if len(parts) != 3:
            return False, None
        
        header_b64, payload_b64, sig_b64 = parts
        
        # Verify signature
        signing_input = f"{header_b64}.{payload_b64}"
        expected_sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
        actual_sig = _b64url_decode(sig_b64)
        
        if not hmac.compare_digest(expected_sig, actual_sig):
            return False, None
        
        # Decode payload
        payload = json.loads(_b64url_decode(payload_b64))
        
        # Check expiration
        if payload.get('exp', 0) < int(time.time()):
            return False, None
        
        return True, payload
    except Exception as e:
        logger.debug(f"[Auth] Token verification failed: {e}")
        return False, None


def create_access_token(user_id: str, email: str, role: str = 'user') -> str:
    """Create an access token for a user."""
    expires = _config.JWT_ACCESS_TOKEN_EXPIRES if _config else 3600
    return create_token({
        'sub': user_id,
        'email': email,
        'role': role,
        'type': 'access',
    }, expires_in=expires)


def create_refresh_token(user_id: str) -> str:
    """Create a refresh token for a user."""
    expires = _config.JWT_REFRESH_TOKEN_EXPIRES if _config else 604800
    return create_token({
        'sub': user_id,
        'type': 'refresh',
    }, expires_in=expires)


# ============================================================
# Input Validation
# ============================================================

def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_password(password: str) -> Tuple[bool, str]:
    """Validate password strength."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"
    return True, "Valid"


# ============================================================
# Flask Route Decorator
# ============================================================

def require_auth(f):
    """Decorator that requires JWT authentication for Flask routes.
    Skipped when AUTH_ENABLED=false."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not _config or not _config.AUTH_ENABLED:
            # Auth disabled — allow all requests
            kwargs['current_user'] = None
            return f(*args, **kwargs)

        from flask import request, jsonify
        
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
        
        token = auth_header.split(' ', 1)[1]
        valid, payload = verify_token(token)
        
        if not valid:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        if payload.get('type') != 'access':
            return jsonify({'error': 'Invalid token type'}), 401
        
        kwargs['current_user'] = payload
        return f(*args, **kwargs)
    
    return decorated


def require_admin(f):
    """Decorator that requires admin role."""
    @wraps(f)
    @require_auth
    def decorated(*args, **kwargs):
        user = kwargs.get('current_user')
        if user and user.get('role') != 'admin':
            from flask import jsonify
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


# ============================================================
# Socket.IO Authentication
# ============================================================

def authenticate_socket(data: Dict) -> Tuple[bool, Optional[Dict]]:
    """Authenticate a Socket.IO connection using JWT token.
    Returns (authenticated, user_payload)."""
    if not _config or not _config.AUTH_ENABLED:
        return True, None  # Auth disabled

    token = data.get('token', '') if data else ''
    if not token:
        return False, None

    valid, payload = verify_token(token)
    if not valid:
        return False, None
    
    if payload.get('type') != 'access':
        return False, None
    
    return True, payload


# ============================================================
# Auth Route Handlers (to be registered with Flask app)
# ============================================================

def register_auth_routes(app):
    """Register authentication REST endpoints with the Flask app."""
    from flask import request, jsonify

    @app.route('/api/auth/register', methods=['POST'])
    def auth_register():
        """Register a new user."""
        if not _config or not _config.AUTH_ENABLED:
            return jsonify({'error': 'Authentication is not enabled'}), 400
        
        if not _db_module or not _db_module._db_available:
            return jsonify({'error': 'Database not available for registration'}), 503

        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400

        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        display_name = data.get('display_name', '').strip()

        # Validate
        if not validate_email(email):
            return jsonify({'error': 'Invalid email format'}), 400

        valid, msg = validate_password(password)
        if not valid:
            return jsonify({'error': msg}), 400

        # Check if user exists
        existing = _db_module.get_user_by_email(email)
        if existing:
            return jsonify({'error': 'Email already registered'}), 409

        # Create user
        pw_hash = hash_password(password)
        user = _db_module.create_user(email, pw_hash, display_name or None)
        if not user:
            return jsonify({'error': 'Failed to create user'}), 500

        # Generate tokens
        access_token = create_access_token(user['id'], email)
        refresh_token = create_refresh_token(user['id'])

        return jsonify({
            'user': user,
            'access_token': access_token,
            'refresh_token': refresh_token,
        }), 201

    @app.route('/api/auth/login', methods=['POST'])
    def auth_login():
        """Login and get JWT tokens."""
        if not _config or not _config.AUTH_ENABLED:
            return jsonify({'error': 'Authentication is not enabled'}), 400
        
        if not _db_module or not _db_module._db_available:
            return jsonify({'error': 'Database not available'}), 503

        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400

        email = data.get('email', '').strip().lower()
        password = data.get('password', '')

        user = _db_module.get_user_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            return jsonify({'error': 'Invalid email or password'}), 401

        if not user.is_active:
            return jsonify({'error': 'Account is deactivated'}), 403

        # Update last login
        _db_module.update_user_login(user.id)

        # Generate tokens
        access_token = create_access_token(user.id, user.email, user.role)
        refresh_token = create_refresh_token(user.id)

        return jsonify({
            'user': user.to_dict(),
            'access_token': access_token,
            'refresh_token': refresh_token,
        })

    @app.route('/api/auth/refresh', methods=['POST'])
    def auth_refresh():
        """Refresh access token using refresh token."""
        if not _config or not _config.AUTH_ENABLED:
            return jsonify({'error': 'Authentication is not enabled'}), 400

        data = request.get_json()
        refresh_token = data.get('refresh_token', '') if data else ''

        valid, payload = verify_token(refresh_token)
        if not valid or payload.get('type') != 'refresh':
            return jsonify({'error': 'Invalid refresh token'}), 401

        user_id = payload.get('sub')
        user = _db_module.get_user_by_id(user_id) if _db_module else None
        if not user:
            return jsonify({'error': 'User not found'}), 404

        access_token = create_access_token(user.id, user.email, user.role)
        return jsonify({'access_token': access_token})

    @app.route('/api/auth/me', methods=['GET'])
    @require_auth
    def auth_me(current_user=None):
        """Get current user profile."""
        if not current_user:
            return jsonify({'user': None})
        
        if _db_module:
            user = _db_module.get_user_by_id(current_user.get('sub'))
            if user:
                return jsonify({'user': user.to_dict()})
        
        return jsonify({'user': current_user})

    @app.route('/api/auth/history', methods=['GET'])
    @require_auth
    def auth_history(current_user=None):
        """Get current user's conversation history."""
        if not current_user or not _db_module:
            return jsonify({'conversations': []})
        
        limit = request.args.get('limit', 20, type=int)
        history = _db_module.get_user_conversation_history(current_user.get('sub'), limit)
        return jsonify({'conversations': history})

    logger.info("[Auth] Auth routes registered: /api/auth/register, /api/auth/login, /api/auth/refresh, /api/auth/me, /api/auth/history")
