"""
REFLECTA — Pydantic Schemas
Request/response validation for all endpoints.
"""

from datetime import date, datetime
from pydantic import BaseModel, Field, field_validator


# ─── AUTH ────────────────────────────────────────────────────────
class UserCreate(BaseModel):
    email: str
    name: str
    password: str
    coach_tone: str = Field(
        default="balanced",
        pattern="^(blunt|balanced|push)$",
        description="Coaching personality: blunt, balanced, or push",
    )


class UserLogin(BaseModel):
    email: str
    password: str


class UserProfileOut(BaseModel):
    id: int
    email: str
    name: str
    avatar_url: str | None = None
    coach_tone: str
    onboarding_complete: bool


class UpdateProfile(BaseModel):
    name: str | None = None
    coach_tone: str | None = Field(
        default=None,
        pattern="^(blunt|balanced|push)$",
    )


class UpdatePassword(BaseModel):
    current_password: str
    new_password: str


# ─── ONBOARDING ─────────────────────────────────────────────────
class OnboardingCreate(BaseModel):
    life_area_focus: str = Field(
        ..., max_length=500,
        description="What is the #1 area of your life you want to fix?",
    )
    past_failures: str = Field(
        ..., max_length=1000,
        description="What have you tried before that didn't work?",
    )
    ideal_day: str = Field(
        ..., max_length=1000,
        description="Describe your ideal day in detail.",
    )
    biggest_excuse: str = Field(
        ..., max_length=500,
        description="What is your #1 recurring excuse?",
    )
    life_scores: dict = Field(
        ...,
        description="Self-assessment scores: {work, health, relationships, mindset, finance, purpose}",
    )

    @field_validator("life_scores")
    @classmethod
    def validate_life_scores(cls, v):
        required_keys = {"work", "health", "relationships", "mindset", "finance", "purpose"}
        if not required_keys.issubset(v.keys()):
            raise ValueError(f"life_scores must contain keys: {required_keys}")
        for key, val in v.items():
            if not (1 <= val <= 10):
                raise ValueError(f"life_scores.{key} must be between 1 and 10")
        return v


class OnboardingOut(BaseModel):
    life_area_focus: str
    past_failures: str
    ideal_day: str
    biggest_excuse: str
    life_scores: dict
    created_at: datetime

    class Config:
        from_attributes = True


# ─── DAILY LOGS (morning + evening) ─────────────────────────────
class MorningLogCreate(BaseModel):
    morning_feeling_score: int = Field(..., ge=1, le=10, description="How are you feeling? 1-10")
    morning_text: str = Field(..., max_length=2000, description="Free-form morning journal entry")

    @field_validator("morning_text")
    @classmethod
    def strip_text(cls, v):
        return v.strip() if v else v


class EveningLogCreate(BaseModel):
    evening_text: str = Field(..., max_length=2000, description="Free-form evening journal entry")
    day_score: int = Field(..., ge=1, le=10, description="Overall day rating 1-10")

    @field_validator("evening_text")
    @classmethod
    def strip_text(cls, v):
        return v.strip() if v else v


class DailyLogOut(BaseModel):
    id: int
    log_date: date
    morning_feeling_score: int | None = None
    morning_text: str | None = None
    morning_extracted: dict | None = None
    evening_text: str | None = None
    evening_extracted: dict | None = None
    day_score: int | None = None
    created_at: datetime

    class Config:
        from_attributes = True


# ─── GOALS ───────────────────────────────────────────────────────
class GoalCreate(BaseModel):
    title: str = Field(..., max_length=300)
    category: str = Field(
        ...,
        pattern="^(health|career|mindset|relationships|finance|purpose)$",
    )
    target_date: date | None = None


class GoalOut(BaseModel):
    id: int
    title: str
    category: str
    created_date: date
    target_date: date | None = None
    is_active: bool

    class Config:
        from_attributes = True


class GoalSkipRequest(BaseModel):
    skip_reason: str = Field(
        default="",
        max_length=500,
        description="Why are you skipping this goal today?",
    )


class GoalConsistencyOut(BaseModel):
    goal_id: int
    title: str
    category: str
    total_days: int
    completed_days: int
    skipped_days: int
    incomplete_days: int
    completion_rate: float


# ─── AI ──────────────────────────────────────────────────────────
class AIAdviceOut(BaseModel):
    id: int
    advice_text: str
    advice_type: str
    given_at: datetime
    validated: bool
    effectiveness_score: float | None = None

    class Config:
        from_attributes = True


class PersonModelOut(BaseModel):
    top_excuses: list | None = None
    consistency_style: str | None = None
    peak_performance_days: list | None = None
    goal_dna: dict | None = None
    life_area_scores: dict | None = None
    dominant_emotions: dict | None = None
    mood_performance_correlation: float | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class AdviceValidationOut(BaseModel):
    id: int
    advice_text: str
    advice_type: str
    given_at: datetime
    validated: bool
    effectiveness_score: float | None = None
    outcome_notes: str | None = None

    class Config:
        from_attributes = True


# ─── ANALYTICS ───────────────────────────────────────────────────
class LifeRadarOut(BaseModel):
    health: float = 0
    career: float = 0
    mindset: float = 0
    relationships: float = 0
    finance: float = 0
    purpose: float = 0


class MoodTrendPoint(BaseModel):
    date: date
    morning_score: int | None = None
    day_score: int | None = None


class WeeklyCardOut(BaseModel):
    week_number: int
    persona_name: str
    goal_completion: str
    mood_trend: str
    best_day: str
    biggest_win: str
    life_area_highlight: str
    coach_says: str
    streak: int
