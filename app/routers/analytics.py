from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.models import DailyLog, MonthlyAnalytics
from app.analytics import generate_monthly_summary
from app.dependencies import get_current_user_id
from app.database.db import get_db
from app.schemas import MonthlyAnalyticsResponse
from app.cache.monthly_analytics_cache import (
    get_monthly_analytics_cache,
    set_monthly_analytics_cache,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/monthly", response_model=MonthlyAnalyticsResponse)
def get_monthly_analytics(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    today = datetime.utcnow()
    month_key = today.strftime("%Y-%m")

    # ---------- CACHE ----------
    cached = get_monthly_analytics_cache(user_id, today.year, today.month)
    if cached:
        return cached

    # ---------- FETCH LOGS ----------
    logs = (
        db.query(DailyLog)
        .filter(DailyLog.user_id == user_id)
        .order_by(DailyLog.created_at.asc())
        .all()
    )

    if not logs:
        raise HTTPException(status_code=400, detail="Not enough data")

    # ---------- DAILY DATA FOR CHART ----------
    daily_data = [
        {
            "day": l.created_at.day,
            "mood": l.mood_score,
            "sleep": l.sleep_hours,
            "work": l.work_hours,
            "goals": l.goal_completed_percentage,
        }
        for l in logs
    ]

    # ---------- SUMMARY ----------
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

    # ---------- STORE MONTHLY ----------
    analytics = MonthlyAnalytics(
        user_id=user_id,
        month=month_key,
        summary=summary,
    )

    db.merge(analytics)
    db.commit()

    response = {
        "month": month_key,
        "summary": summary,
        "daily_data": daily_data,
    }

    set_monthly_analytics_cache(user_id, today.year, today.month, response)

    return response
