from fastapi import APIRouter, Depends, HTTPException, status
from app.database.db import get_db
from app.database.models import AIFeedback, AIFeedback, DailyAIMotivation
from app.dependencies import get_current_user_id # your JWT dependency
from sqlalchemy.orm import Session
from datetime import datetime

router = APIRouter(prefix="/daily-ai-motivation", tags=["Daily AI Motivation"])


@router.get("/today")
def get_today_motivation(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    today = datetime.today().date()

    motivation = db.query(DailyAIMotivation).filter(
        DailyAIMotivation.user_id == user_id,
        DailyAIMotivation.date == today
    ).first()

    if not motivation:
        raise HTTPException(
            status_code=404,
            detail="No motivation found for today"
        )

    # Check if feedback already exists
    existing_feedback = db.query(AIFeedback).filter(
        AIFeedback.user_id == user_id,
        AIFeedback.source == "daily_motivation", 
        AIFeedback.source_id == motivation.id
    ).first()

    return {
        "id": motivation.id,
        "insight": motivation.insight,  # or motivation.message (use your correct field)
        "date": motivation.date,
        "feedbackGiven": existing_feedback is not None
    }