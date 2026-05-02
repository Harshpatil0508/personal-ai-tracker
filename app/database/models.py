"""
REFLECTA — Database Models
"The AI that knows you better than you know yourself"
"""

import enum
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, Enum,
    Float, ForeignKey, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.database import Base


# ─── ENUMS ───────────────────────────────────────────────────────
class CoachTone(str, enum.Enum):
    blunt    = "blunt"
    balanced = "balanced"
    push     = "push"


class GoalCategory(str, enum.Enum):
    health        = "health"
    career        = "career"
    mindset       = "mindset"
    relationships = "relationships"
    finance       = "finance"
    purpose       = "purpose"


class GoalLogStatus(str, enum.Enum):
    completed  = "completed"
    incomplete = "incomplete"
    skipped    = "skipped"


class AdviceType(str, enum.Enum):
    daily   = "daily"
    weekly  = "weekly"
    monthly = "monthly"


class MemoryType(str, enum.Enum):
    journal   = "journal"
    advice    = "advice"
    pattern   = "pattern"
    milestone = "milestone"


# ─── USERS ───────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id             = Column(Integer, primary_key=True)
    email          = Column(String, unique=True, index=True, nullable=False)
    name           = Column(String, nullable=False)
    password_hash  = Column(String, nullable=False)
    role           = Column(String, default="user")
    token_version  = Column(Integer, default=1)

    # Reflecta-specific
    coach_tone          = Column(Enum(CoachTone), default=CoachTone.balanced)
    onboarding_complete = Column(Boolean, default=False)

    # Avatar
    avatar_url = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ──
    refresh_tokens      = relationship("RefreshToken",      back_populates="user", cascade="all, delete")
    onboarding          = relationship("UserOnboarding",    back_populates="user", uselist=False, cascade="all, delete-orphan")
    daily_logs          = relationship("DailyLog",          back_populates="user", cascade="all, delete-orphan")
    goals               = relationship("Goal",              back_populates="user", cascade="all, delete-orphan")
    ai_advice           = relationship("AIAdvice",          back_populates="user", cascade="all, delete-orphan")
    person_model        = relationship("PersonModel",       back_populates="user", uselist=False, cascade="all, delete-orphan")
    memory_embeddings   = relationship("MemoryEmbedding",   back_populates="user", cascade="all, delete-orphan")
    dead_letter_tasks   = relationship("DeadLetterTask",    back_populates="user", cascade="all, delete-orphan")


# ─── ONBOARDING (captured once at signup) ────────────────────────
class UserOnboarding(Base):
    __tablename__ = "user_onboarding"

    id      = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    life_area_focus  = Column(Text)         # "What #1 area to fix?"
    past_failures    = Column(Text)         # "What have you tried before?"
    ideal_day        = Column(Text)         # "Describe your ideal day"
    biggest_excuse   = Column(Text)         # "Your #1 recurring excuse"
    life_scores      = Column(JSONB)        # {work:6, health:4, relationships:7, mindset:5}

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", back_populates="onboarding")


# ─── DAILY LOGS (morning + evening) ─────────────────────────────
class DailyLog(Base):
    __tablename__ = "daily_logs"

    __table_args__ = (
        UniqueConstraint("user_id", "log_date", name="uq_user_daily_log"),
    )

    id      = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    log_date = Column(Date, nullable=False)

    # ── Morning check-in ──
    morning_feeling_score = Column(Integer)                  # 1-10 slider
    morning_text          = Column(Text)                     # free-form journal
    morning_extracted     = Column(JSONB)                    # AI-extracted: {mood, energy, stressors, intent_score}

    # ── Evening check-in ──
    evening_text          = Column(Text)                     # free-form journal
    evening_extracted     = Column(JSONB)                    # AI-extracted: {outcome, energy, mood, guilt_flags}
    day_score             = Column(Integer)                  # overall day rating 1-10

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", back_populates="daily_logs")
    goal_logs = relationship("DailyGoalLog", back_populates="daily_log", cascade="all, delete-orphan")


# ─── GOALS ───────────────────────────────────────────────────────
class Goal(Base):
    __tablename__ = "goals"

    id       = Column(Integer, primary_key=True)
    user_id  = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    title       = Column(Text, nullable=False)
    category    = Column(Enum(GoalCategory), nullable=False)
    created_date = Column(Date, default=lambda: datetime.now(timezone.utc).date())
    target_date  = Column(Date, nullable=True)
    is_active    = Column(Boolean, default=True)

    user      = relationship("User", back_populates="goals")
    goal_logs = relationship("DailyGoalLog", back_populates="goal", cascade="all, delete-orphan")


# ─── DAILY GOAL LOGS ────────────────────────────────────────────
class DailyGoalLog(Base):
    __tablename__ = "daily_goal_logs"

    __table_args__ = (
        UniqueConstraint("goal_id", "log_date", name="uq_goal_log_per_day"),
    )

    id      = Column(Integer, primary_key=True)
    goal_id = Column(Integer, ForeignKey("goals.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    log_date = Column(Date, nullable=False)

    status      = Column(Enum(GoalLogStatus), nullable=False)
    skip_reason = Column(Text, nullable=True)        # captured silently if skipped

    daily_log_id = Column(Integer, ForeignKey("daily_logs.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    goal      = relationship("Goal",     back_populates="goal_logs")
    daily_log = relationship("DailyLog", back_populates="goal_logs")


# ─── AI ADVICE ───────────────────────────────────────────────────
class AIAdvice(Base):
    __tablename__ = "ai_advice"

    id      = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    advice_text  = Column(Text, nullable=False)
    advice_type  = Column(Enum(AdviceType), nullable=False, default=AdviceType.daily)

    given_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    validate_at  = Column(DateTime(timezone=True))       # given_at + 14 days
    validated    = Column(Boolean, default=False)
    effectiveness_score = Column(Float, nullable=True)   # 0-1, calculated post-validation
    outcome_notes       = Column(Text, nullable=True)

    user = relationship("User", back_populates="ai_advice")


# ─── PERSON MODEL (updated by Celery jobs) ──────────────────────
class PersonModel(Base):
    __tablename__ = "person_model"

    id      = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    top_excuses                  = Column(JSONB)     # ["I was tired", "Too busy"]
    consistency_style            = Column(String)     # "burst_worker" | "steady" | "fading"
    peak_performance_days        = Column(JSONB)      # ["Wednesday", "Thursday"]
    goal_dna                     = Column(JSONB)      # {starter_energy: 0.8, followthrough: 0.5}
    life_area_scores             = Column(JSONB)      # {health:62, career:78, ...}
    dominant_emotions            = Column(JSONB)      # {ambition:12, stress:8, joy:5}
    mood_performance_correlation = Column(Float)

    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", back_populates="person_model")


# ─── VECTOR MEMORY (pgvector) ───────────────────────────────────
class MemoryEmbedding(Base):
    __tablename__ = "memory_embeddings"

    __table_args__ = (
        UniqueConstraint("user_id", "memory_type", "content", name="uq_user_memory"),
    )

    id      = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    content     = Column(Text, nullable=False)
    embedding   = Column(Vector(768), nullable=False)   # JINA embedding dimension
    memory_type = Column(Enum(MemoryType), nullable=False, default=MemoryType.journal)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    user = relationship("User", back_populates="memory_embeddings")


# ─── AUTH ────────────────────────────────────────────────────────
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id         = Column(Integer, primary_key=True)
    token_hash = Column(String, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    expires_at = Column(DateTime)

    user = relationship("User", back_populates="refresh_tokens")


# ─── DEAD LETTER QUEUE ──────────────────────────────────────────
class DeadLetterTask(Base):
    __tablename__ = "dead_letter_tasks"

    id      = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    source     = Column(String(100), nullable=False)
    error      = Column(Text, nullable=False)
    status     = Column(String(20), default="failed")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="dead_letter_tasks")