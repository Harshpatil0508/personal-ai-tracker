from sqlalchemy import Column, Integer, String, Float, Numeric, Date, Text,DateTime, ForeignKey
from app.database import Base
from sqlalchemy.orm import relationship

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    password_hash = Column(String)
    role = Column(String, default="user")  # user | admin
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete")

class DailyLog(Base):
    __tablename__ = "daily_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, index=True)
    date = Column(Date)

    work_hours = Column(Float)
    study_hours = Column(Float)
    sleep_hours = Column(Float)

    mood_score = Column(Integer)
    goal_completed_percentage = Column(
        Numeric(5, 2), nullable=False
    ) 
    notes = Column(Text)

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)
    token_hash = Column(String, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    expires_at = Column(DateTime)

    user = relationship("User", back_populates="refresh_tokens")