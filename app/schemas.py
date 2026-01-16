from pydantic import BaseModel,Field
from datetime import date
from typing import Optional

class UserCreate(BaseModel):
    email: str
    name: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str
    
class DailyLogCreate(BaseModel):
    # date: date
    work_hours: float
    study_hours: float
    sleep_hours: float
    mood_score: int
    goal_completed_percentage: float = Field(
        ..., ge=0, le=100, description="Goal completion percentage (0-100)"
    )
    notes: str
class DailyLogUpdate(BaseModel):
    work_hours: Optional[float] = None
    study_hours: Optional[float] = None
    sleep_hours: Optional[float] = None
    mood_score: Optional[int] = None
    goal_completed_percentage: Optional[float] = Field(
        default=None, ge=0, le=100, description="Goal completion percentage (0-100)"
    )
    notes: Optional[str] = None
class MonthlyAnalyticsResponse(BaseModel):
    month: str
    summary: dict

class AIFeedbackCreate(BaseModel):
    source: str
    source_id: int
    is_helpful: bool
