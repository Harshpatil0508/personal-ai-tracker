import json
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
    db: Session = Depends(get_db)
):
    today = datetime.today()
    year = today.year
    month = today.month
    month_key = today.strftime("%Y-%m")

    # ---------- 1️⃣ REDIS CACHE FIRST ----------
    cached = get_monthly_analytics_cache(user_id, year, month)
    if cached:
        return cached

    # ---------- 2️⃣ DB CHECK (PERSISTED ANALYTICS) ----------
    analytics = (
        db.query(MonthlyAnalytics)
        .filter(
            MonthlyAnalytics.user_id == user_id,
            MonthlyAnalytics.month == month_key
        )
        .first()
    )

    if analytics:
        response = {
            "month": month_key,
            "summary": analytics.summary
        }

        # Cache DB result
        set_monthly_analytics_cache(user_id, year, month, response)
        return response

    # ---------- 3️⃣ COMPUTE FROM DAILY LOGS ----------
    logs = (
        db.query(DailyLog)
        .filter(DailyLog.user_id == user_id)
        .all()
    )

    if not logs:
        raise HTTPException(status_code=400, detail="Not enough data")

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

    # ---------- 4️⃣ STORE IN DB ----------
    analytics = MonthlyAnalytics(
        user_id=user_id,
        month=month_key,
        summary=summary
    )

    db.add(analytics)
    db.commit()

    response = {
        "month": month_key,
        "summary": summary
    }

    # ---------- 5️⃣ STORE IN REDIS ----------
    set_monthly_analytics_cache(user_id, year, month, response)

    return response
