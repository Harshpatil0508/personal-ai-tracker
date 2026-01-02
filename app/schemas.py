from pydantic import BaseModel,Field
from datetime import date

class DailyLogCreate(BaseModel):
    date: date
    work_hours: float
    study_hours: float
    sleep_hours: float
    mood_score: int
    goal_completed_percentage: float = Field(
        ..., ge=0, le=100, description="Goal completion percentage (0-100)"
    )
    notes: str
