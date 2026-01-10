from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.models import DailyLog, MonthlyAnalytics
from app.analytics import generate_monthly_summary
from app.dependencies import get_current_user_id
from app.db import get_db
from app.schemas import MonthlyAnalyticsResponse

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/monthly", response_model=MonthlyAnalyticsResponse)
def get_monthly_analytics(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    today = datetime.today()
    month_key = today.strftime("%Y-%m")

    # Check if already generated
    analytics = (
        db.query(MonthlyAnalytics)
        .filter(
            MonthlyAnalytics.user_id == user_id,
            MonthlyAnalytics.month == month_key
        )
        .first()
    )

    if analytics:
        return {
            "month": month_key,
            "summary": analytics.summary
        }

    # Fetch daily logs
    logs = (
        db.query(DailyLog)
        .filter(DailyLog.user_id == user_id)
        .all()
    )

    logs_data = [
        {
            "work_hours": l.work_hours,
            "study_hours": l.study_hours,
            "sleep_hours": l.sleep_hours,
            "goal_completed": l.goal_completed_percentage,
            "mood_score": l.mood_score,
        }
        for l in logs
    ]

    summary = generate_monthly_summary(logs_data)

    if not summary:
        raise HTTPException(status_code=400, detail="Not enough data")

    analytics = MonthlyAnalytics(
        user_id=user_id,
        month=month_key,
        summary=summary
    )

    db.add(analytics)
    db.commit()

    return {
        "month": month_key,
        "summary": summary
    }
