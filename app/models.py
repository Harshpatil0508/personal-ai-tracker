from datetime import datetime,timezone
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, String, Float, Numeric, Date, Text,DateTime, ForeignKey, JSON,UniqueConstraint
from app.database import Base
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
    message = Column(Text)
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
    content = Column(Text, nullable=False)
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
