"""
PostgreSQL Database Layer
==========================
SQLAlchemy models for persistent storage of users, conversations, analytics.
Blueprint Section 8: State Management — PostgreSQL for durable conversation logs.

Gracefully degrades to no-op when DATABASE_URL is not configured.
"""
import os
import time
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

# SQLAlchemy instances (initialized lazily)
db = None
_db_available = False
_config = None


def init_database(app, config):
    """Initialize PostgreSQL database connection and create tables."""
    global db, _db_available, _config
    _config = config

    logger.info("[Database] Initializing database...")
    logger.info(f"[Database] DATABASE_ENABLED: {config.DATABASE_ENABLED}")
    logger.info(f"[Database] SQLALCHEMY_DATABASE_URI: {config.DATABASE_URL}")

    if not config.DATABASE_ENABLED:
        logger.info("[Database] DATABASE_URL not configured — persistence disabled")
        return False

    try:
        from flask_sqlalchemy import SQLAlchemy

        app.config['SQLALCHEMY_DATABASE_URI'] = config.get_sqlalchemy_uri()
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = config.SQLALCHEMY_ENGINE_OPTIONS

        db = SQLAlchemy(app)
        _define_models()
        
        with app.app_context():
            db.create_all()
        
        _db_available = True
        logger.info(f"[Database] Connected to PostgreSQL, tables created")
        return True

    except ImportError:
        logger.warning("[Database] flask-sqlalchemy not installed — persistence disabled")
        return False
    except Exception as e:
        logger.warning(f"[Database] Connection failed ({e}) — persistence disabled")
        return False


# ============================================================
# SQLAlchemy Models
# ============================================================

User = None
Conversation = None
ConversationMessage = None
AnalyticsEvent = None


def _define_models():
    """Define SQLAlchemy models. Must be called after db is initialized."""
    global User, Conversation, ConversationMessage, AnalyticsEvent

    class _User(db.Model):
        __tablename__ = 'users'

        id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        email = db.Column(db.String(255), unique=True, nullable=False, index=True)
        password_hash = db.Column(db.String(255), nullable=False)
        display_name = db.Column(db.String(100), nullable=True)
        created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
        last_login = db.Column(db.DateTime, nullable=True)
        is_active = db.Column(db.Boolean, default=True)
        role = db.Column(db.String(20), default='user')  # user, admin
        preferences = db.Column(db.JSON, default=dict)

        # Relationships
        conversations = db.relationship('Conversation', backref='user', lazy='dynamic')

        def to_dict(self):
            return {
                'id': self.id,
                'email': self.email,
                'display_name': self.display_name,
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'last_login': self.last_login.isoformat() if self.last_login else None,
                'role': self.role,
            }

    class _Conversation(db.Model):
        __tablename__ = 'conversations'

        id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=True, index=True)
        session_id = db.Column(db.String(100), nullable=True, index=True)
        mode = db.Column(db.String(20), nullable=False)  # interview, language, helpdesk
        language = db.Column(db.String(10), default='en')
        started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
        ended_at = db.Column(db.DateTime, nullable=True)
        duration_seconds = db.Column(db.Integer, nullable=True)
        exchange_count = db.Column(db.Integer, default=0)
        emotional_tone_summary = db.Column(db.JSON, default=dict)
        feedback_rating = db.Column(db.Integer, nullable=True)  # 1-5 stars
        feedback_text = db.Column(db.Text, nullable=True)
        metadata_ = db.Column('metadata', db.JSON, default=dict)

        # Relationships
        messages = db.relationship('ConversationMessage', backref='conversation',
                                   lazy='dynamic', order_by='ConversationMessage.sequence')

        def to_dict(self, include_messages=False):
            result = {
                'id': self.id,
                'user_id': self.user_id,
                'mode': self.mode,
                'language': self.language,
                'started_at': self.started_at.isoformat() if self.started_at else None,
                'ended_at': self.ended_at.isoformat() if self.ended_at else None,
                'duration_seconds': self.duration_seconds,
                'exchange_count': self.exchange_count,
                'feedback_rating': self.feedback_rating,
            }
            if include_messages:
                result['messages'] = [m.to_dict() for m in self.messages.all()]
            return result

    class _ConversationMessage(db.Model):
        __tablename__ = 'conversation_messages'

        id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        conversation_id = db.Column(db.String(36), db.ForeignKey('conversations.id'), nullable=False, index=True)
        sequence = db.Column(db.Integer, nullable=False)
        role = db.Column(db.String(20), nullable=False)  # user, assistant, system
        content = db.Column(db.Text, nullable=False)
        created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
        audio_duration_ms = db.Column(db.Integer, nullable=True)
        token_count = db.Column(db.Integer, nullable=True)
        was_interrupted = db.Column(db.Boolean, default=False)
        emotional_tone = db.Column(db.String(20), nullable=True)
        latency_ms = db.Column(db.Integer, nullable=True)

        def to_dict(self):
            return {
                'id': self.id,
                'sequence': self.sequence,
                'role': self.role,
                'content': self.content[:500],  # Truncate for API responses
                'created_at': self.created_at.isoformat() if self.created_at else None,
                'was_interrupted': self.was_interrupted,
                'emotional_tone': self.emotional_tone,
            }

    class _AnalyticsEvent(db.Model):
        __tablename__ = 'analytics_events'

        id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
        event_type = db.Column(db.String(50), nullable=False, index=True)
        user_id = db.Column(db.String(36), nullable=True, index=True)
        session_id = db.Column(db.String(100), nullable=True)
        conversation_id = db.Column(db.String(36), nullable=True)
        data = db.Column(db.JSON, default=dict)
        created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

        def to_dict(self):
            return {
                'id': self.id,
                'event_type': self.event_type,
                'data': self.data,
                'created_at': self.created_at.isoformat() if self.created_at else None,
            }

    User = _User
    Conversation = _Conversation
    ConversationMessage = _ConversationMessage
    AnalyticsEvent = _AnalyticsEvent


# ============================================================
# Database Operations (No-op if DB not available)
# ============================================================

def log_conversation_start(session_id: str, mode: str, language: str = 'en',
                           user_id: str = None) -> Optional[str]:
    """Log the start of a new conversation. Returns conversation ID."""
    if not _db_available:
        return None
    try:
        conv = Conversation(
            session_id=session_id,
            user_id=user_id,
            mode=mode,
            language=language,
        )
        db.session.add(conv)
        db.session.commit()
        logger.debug(f"[Database] Conversation started: {conv.id}")
        return conv.id
    except Exception as e:
        logger.error(f"[Database] log_conversation_start error: {e}")
        db.session.rollback()
        return None


def log_message(conversation_id: str, sequence: int, role: str, content: str,
                was_interrupted: bool = False, emotional_tone: str = None,
                latency_ms: int = None, token_count: int = None):
    """Log a message in a conversation."""
    if not _db_available or not conversation_id:
        return
    try:
        msg = ConversationMessage(
            conversation_id=conversation_id,
            sequence=sequence,
            role=role,
            content=content,
            was_interrupted=was_interrupted,
            emotional_tone=emotional_tone,
            latency_ms=latency_ms,
            token_count=token_count,
        )
        db.session.add(msg)
        db.session.commit()
    except Exception as e:
        logger.error(f"[Database] log_message error: {e}")
        db.session.rollback()


def log_conversation_end(conversation_id: str, exchange_count: int = 0,
                         emotional_summary: Dict = None):
    """Log the end of a conversation."""
    if not _db_available or not conversation_id:
        return
    try:
        conv = db.session.get(Conversation, conversation_id)
        if conv:
            conv.ended_at = datetime.now(timezone.utc)
            conv.exchange_count = exchange_count
            if conv.started_at:
                conv.duration_seconds = int((conv.ended_at - conv.started_at).total_seconds())
            if emotional_summary:
                conv.emotional_tone_summary = emotional_summary
            db.session.commit()
    except Exception as e:
        logger.error(f"[Database] log_conversation_end error: {e}")
        db.session.rollback()


def log_analytics_event(event_type: str, data: Dict = None,
                        user_id: str = None, session_id: str = None,
                        conversation_id: str = None):
    """Log an analytics event."""
    if not _db_available:
        return
    try:
        event = AnalyticsEvent(
            event_type=event_type,
            user_id=user_id,
            session_id=session_id,
            conversation_id=conversation_id,
            data=data or {},
        )
        db.session.add(event)
        db.session.commit()
    except Exception as e:
        logger.error(f"[Database] log_analytics error: {e}")
        db.session.rollback()


def save_feedback(conversation_id: str, rating: int, text: str = None):
    """Save user feedback for a conversation."""
    if not _db_available or not conversation_id:
        return False
    try:
        conv = db.session.get(Conversation, conversation_id)
        if conv:
            conv.feedback_rating = rating
            conv.feedback_text = text
            db.session.commit()
            return True
        return False
    except Exception as e:
        logger.error(f"[Database] save_feedback error: {e}")
        db.session.rollback()
        return False


# ============================================================
# User Management
# ============================================================

def create_user(email: str, password_hash: str, display_name: str = None) -> Optional[Dict]:
    """Create a new user."""
    if not _db_available:
        return None
    try:
        user = User(email=email, password_hash=password_hash, display_name=display_name)
        db.session.add(user)
        db.session.commit()
        return user.to_dict()
    except Exception as e:
        logger.error(f"[Database] create_user error: {e}")
        db.session.rollback()
        return None


def get_user_by_email(email: str) -> Optional[Any]:
    """Get user by email."""
    if not _db_available:
        return None
    try:
        return User.query.filter_by(email=email).first()
    except Exception as e:
        logger.error(f"[Database] get_user_by_email error: {e}")
        return None


def get_user_by_id(user_id: str) -> Optional[Any]:
    """Get user by ID."""
    if not _db_available:
        return None
    try:
        return db.session.get(User, user_id)
    except Exception as e:
        logger.error(f"[Database] get_user_by_id error: {e}")
        return None


def update_user_login(user_id: str):
    """Update user's last login timestamp."""
    if not _db_available:
        return
    try:
        user = db.session.get(User, user_id)
        if user:
            user.last_login = datetime.now(timezone.utc)
            db.session.commit()
    except Exception as e:
        logger.error(f"[Database] update_user_login error: {e}")
        db.session.rollback()


# ============================================================
# Analytics & Reporting
# ============================================================

def get_user_conversation_history(user_id: str, limit: int = 20) -> List[Dict]:
    """Get a user's recent conversations."""
    if not _db_available:
        return []
    try:
        convs = Conversation.query.filter_by(user_id=user_id) \
            .order_by(Conversation.started_at.desc()) \
            .limit(limit).all()
        return [c.to_dict() for c in convs]
    except Exception as e:
        logger.error(f"[Database] get_user_history error: {e}")
        return []


def get_analytics_summary(hours: int = 24) -> Dict:
    """Get analytics summary for the last N hours."""
    if not _db_available:
        return {'status': 'disabled'}
    try:
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        total_conversations = Conversation.query.filter(
            Conversation.started_at >= cutoff
        ).count()

        mode_counts = db.session.query(
            Conversation.mode, db.func.count(Conversation.id)
        ).filter(
            Conversation.started_at >= cutoff
        ).group_by(Conversation.mode).all()

        avg_duration = db.session.query(
            db.func.avg(Conversation.duration_seconds)
        ).filter(
            Conversation.started_at >= cutoff,
            Conversation.duration_seconds.isnot(None)
        ).scalar()

        avg_rating = db.session.query(
            db.func.avg(Conversation.feedback_rating)
        ).filter(
            Conversation.started_at >= cutoff,
            Conversation.feedback_rating.isnot(None)
        ).scalar()

        return {
            'period_hours': hours,
            'total_conversations': total_conversations,
            'conversations_by_mode': {mode: count for mode, count in mode_counts},
            'avg_duration_seconds': round(avg_duration, 1) if avg_duration else None,
            'avg_feedback_rating': round(avg_rating, 2) if avg_rating else None,
        }
    except Exception as e:
        logger.error(f"[Database] get_analytics_summary error: {e}")
        return {'status': 'error', 'message': str(e)}


def get_database_health() -> Dict:
    """Get database health status."""
    if not _config or not _config.DATABASE_ENABLED:
        return {'status': 'disabled', 'message': 'DATABASE_URL not configured'}

    if not _db_available:
        return {'status': 'unhealthy', 'message': 'Database connection failed'}

    try:
        db.session.execute(db.text('SELECT 1'))
        user_count = User.query.count() if User else 0
        conv_count = Conversation.query.count() if Conversation else 0
        return {
            'status': 'healthy',
            'users': user_count,
            'conversations': conv_count,
        }
    except Exception as e:
        return {'status': 'unhealthy', 'message': str(e)}


def get_db_session():
    if db is None:
        logger.error("[Database] The database session is not initialized. Ensure init_database is called successfully.")
        raise RuntimeError("Database session is not initialized.")
    return db.session
