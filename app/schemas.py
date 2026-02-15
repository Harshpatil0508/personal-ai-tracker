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
    
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class DailyLogCreate(BaseModel):
    work_hours: Optional[float] = Field(
        default=0.0,
        ge=0,
        le=24,
        description="Hours worked (0-24)"
    )

    study_hours: Optional[float] = Field(
        default=0.0,
        ge=0,
        le=24,
        description="Hours studied (0-24)"
    )

    sleep_hours: Optional[float] = Field(
        default=None,
        ge=0,
        le=24,
        description="Hours slept (0-24)"
    )

    mood_score: Optional[int] = Field(
        default=None,
        ge=1,
        le=10,
        description="Mood score (1-10)"
    )

    goal_completed_percentage: Optional[float] = Field(
        default=0.0,
        ge=0,
        le=100,
        description="Goal completion % (0-100)"
    )

    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Free text notes (max 1000 chars)"
    )

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, v):
        if v:
            return v.strip()
        return v

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


from pydantic import BaseModel

class UserProfileOut(BaseModel):
    id: int
    email: str
    name: str
    avatar_url: str | None

    daily_reminder: bool
    weekly_digest: bool
    monthly_review: bool
    ai_motivation: bool

class UpdateProfile(BaseModel):
    name: str

class UpdatePassword(BaseModel):
    current_password: str
    new_password: str

class UpdatePreferences(BaseModel):
    daily_reminder: bool
    weekly_digest: bool
    monthly_review: bool
    ai_motivation: bool

class DailyAnalyticsPoint(BaseModel):
    day: int
    mood: float
    sleep: float
    work: float
    goals: float


class MonthlyAnalyticsResponse(BaseModel):
    month: str
    daily_data: list[DailyAnalyticsPoint]
    summary: dict
