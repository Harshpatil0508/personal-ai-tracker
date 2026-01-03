from sqlalchemy import Column, Integer, String, Float, Numeric, Date, Text
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    password_hash = Column(String)

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
