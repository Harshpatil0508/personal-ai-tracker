from datetime import datetime,timezone
from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Column, Integer, String, Float, Numeric, Date, Text,DateTime, ForeignKey, JSON,UniqueConstraint
from app.database.database import Base
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    password_hash = Column(String)
    role = Column(String, default="user")  # user | admin
    token_version = Column(Integer, default=1)
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete")

class DailyLog(Base):
    __tablename__ = "daily_logs"

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_user_daily_log"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)

    work_hours = Column(Float)
    study_hours = Column(Float)
    sleep_hours = Column(Float)

    mood_score = Column(Integer)
    goal_completed_percentage = Column(Numeric(5, 2), nullable=False)
    notes = Column(Text)
    is_auto = Column(Boolean, default=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )


class MonthlyAnalytics(Base):
    __tablename__ = "monthly_analytics"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    month = Column(String, index=True)
    summary = Column(JSON)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)
    token_hash = Column(String, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )   
    expires_at = Column(DateTime)

    user = relationship("User", back_populates="refresh_tokens")


class DailyAIMotivation(Base):
    __tablename__ = "daily_ai_motivation"

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_user_daily_ai"),
    )


    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date)
    # message = Column(Text)
    insight = Column(Text, nullable=False)
    explanation = Column(JSON, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
class MonthlyAIReview(Base):
    __tablename__ = "monthly_ai_reviews"

    __table_args__ = (
        UniqueConstraint("user_id", "month", name="uq_user_month_ai_review"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    month = Column(String(7), nullable=False)  # YYYY-MM
    # content = Column(JSON, nullable=False)
    insight = Column(Text, nullable=False)
    explanation = Column(JSON, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

class AIEmbedding(Base):
    __tablename__ = "ai_embeddings"

    __table_args__ = (
        UniqueConstraint(
            "user_id", "source", "source_id",
            name="uq_user_source_embedding"
        ),
    )

    id = Column(Integer, primary_key=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # What kind of text produced this embedding
    source = Column(
        String,
        nullable=False
    )  # daily_motivation | monthly_review | daily_log | custom_note

    # ID of the source row (daily_ai_motivation.id, monthly_ai_reviews.id, etc.)
    source_id = Column(Integer, nullable=False)

    content = Column(Text, nullable=False)

    embedding = Column(Vector(1024), nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

class AIFeedback(Base):
    __tablename__ = "ai_feedback"

    id = Column(Integer, primary_key=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    source = Column(String, nullable=False)
    source_id = Column(Integer, nullable=False)

    #  true, false
    is_helpful = Column(Boolean, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id", "source", "source_id",
            name="uq_user_ai_feedback"
        ),
    )

class AIBehaviorProfile(Base):
    __tablename__ = "ai_behavior_profiles"

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True
    )
    # preference learnign (from feedback)
    prefers_encouraging = Column(Boolean, default=False)
    prefers_actionable = Column(Boolean, default=False)


    # outcome learning (from delayed validation)
    successful_advice = Column(Integer, default=0)
    failed_advice = Column(Integer, default=0)

    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    avoid_repeating_failed = Column(Boolean, default=False)


class AIValidation(Base):
    __tablename__ = "ai_validation"
    __table_args__ = (
        UniqueConstraint(
            "ai_type", "ai_ref_id", "metric",
            name="uq_ai_validation_once"
        ),
    )

    id = Column(Integer, primary_key=True)

    user_id = Column(Integer, index=True, nullable=False)

    ai_type = Column(String, nullable=False)
    ai_ref_id = Column(Integer, nullable=False)

    metric = Column(String, nullable=False)
    # sleep_hours | work_hours | mood_score | goal_completed_percentage

    before_value = Column(Float)
    after_value = Column(Float)
    delta = Column(Float)
    result = Column(String, nullable=False)
    # improved | neutral | declined
    validated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True
    )
