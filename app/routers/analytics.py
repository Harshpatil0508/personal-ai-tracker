"""
REFLECTA — Analytics Router
Life radar, mood trends, weekly persona cards, and dashboard stats.
"""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.models import (
    User, UserOnboarding, DailyLog, Goal, DailyGoalLog,
    AIAdvice, PersonModel, GoalLogStatus, AdviceType,
)
from app.schemas import LifeRadarOut, MoodTrendPoint, WeeklyCardOut
from app.dependencies import get_current_user_id
from app.database.db import get_db
from app.ai import generate_weekly_persona

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


# ─── LIFE RADAR (6-axis spider chart) ───────────────────────────
@router.get("/life-radar", response_model=LifeRadarOut)
def get_life_radar(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Returns normalized 0-10 scores for the 6 life areas
    based on goal completion rates and journal data.
    """
    goals = db.query(Goal).filter(Goal.user_id == user_id, Goal.is_active == True).all()
    thirty_days_ago = datetime.today().date() - timedelta(days=30)

    category_scores = {}
    for goal in goals:
        cat = goal.category.value if hasattr(goal.category, 'value') else goal.category
        logs = (
            db.query(DailyGoalLog)
            .filter(
                DailyGoalLog.goal_id == goal.id,
                DailyGoalLog.log_date >= thirty_days_ago,
            )
            .all()
        )

        if not logs:
            continue

        completed = sum(1 for l in logs if l.status == GoalLogStatus.completed)
        rate = completed / len(logs)

        if cat not in category_scores:
            category_scores[cat] = []
        category_scores[cat].append(rate * 10)

    # Average per category
    result = {}
    for cat in ["health", "career", "mindset", "relationships", "finance", "purpose"]:
        if cat in category_scores:
            result[cat] = round(sum(category_scores[cat]) / len(category_scores[cat]), 1)
        else:
            # Check onboarding scores as fallback
            onboarding = db.query(UserOnboarding).filter_by(user_id=user_id).first()
            if onboarding and onboarding.life_scores:
                key_map = {"career": "work"}
                look_key = key_map.get(cat, cat)
                result[cat] = onboarding.life_scores.get(look_key, 0)
            else:
                result[cat] = 0

    return LifeRadarOut(**result)


# ─── MOOD TRENDS ────────────────────────────────────────────────
@router.get("/mood-trends", response_model=list[MoodTrendPoint])
def get_mood_trends(
    days: int = 30,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get daily mood scores for charting."""
    start_date = datetime.today().date() - timedelta(days=days)

    logs = (
        db.query(DailyLog)
        .filter(
            DailyLog.user_id == user_id,
            DailyLog.log_date >= start_date,
        )
        .order_by(DailyLog.log_date.asc())
        .all()
    )

    return [
        MoodTrendPoint(
            date=log.log_date,
            morning_score=log.morning_feeling_score,
            day_score=log.day_score,
        )
        for log in logs
    ]


# ─── GOAL DNA ───────────────────────────────────────────────────
@router.get("/goal-dna")
def get_goal_dna(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get the specific Goal DNA metrics from the person model."""
    person = db.query(PersonModel).filter_by(user_id=user_id).first()
    if not person or not person.goal_dna:
        return {"starter_energy": 0, "followthrough": 0, "recovery_speed": 0, "best_goal_type": "None"}
    return person.goal_dna


# ─── WEEKLY PERSONA CARD ────────────────────────────────────────
@router.get("/weekly-card", response_model=WeeklyCardOut)
def get_weekly_card(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Generate this week's persona card with AI-assigned persona name."""
    today = datetime.today().date()
    week_start = today - timedelta(days=today.weekday())

    # Week's logs
    logs = (
        db.query(DailyLog)
        .filter(
            DailyLog.user_id == user_id,
            DailyLog.log_date >= week_start,
        )
        .all()
    )

    # Week's goal logs
    goal_logs = (
        db.query(DailyGoalLog)
        .filter(
            DailyGoalLog.user_id == user_id,
            DailyGoalLog.log_date >= week_start,
        )
        .all()
    )

    # Calculate stats
    total_goals = len(goal_logs) or 1
    completed = sum(1 for gl in goal_logs if gl.status == GoalLogStatus.completed)
    skipped = sum(1 for gl in goal_logs if gl.status == GoalLogStatus.skipped)
    completion_pct = round(completed / total_goals * 100)

    morning_scores = [l.morning_feeling_score for l in logs if l.morning_feeling_score]
    day_scores = [l.day_score for l in logs if l.day_score]

    # Best day
    best_day = "N/A"
    if day_scores and logs:
        best_log = max(
            [l for l in logs if l.day_score],
            key=lambda l: l.day_score,
            default=None,
        )
        if best_log:
            best_day = best_log.log_date.strftime("%A")

    # Mood trend
    if len(morning_scores) >= 2:
        if morning_scores[-1] > morning_scores[0]:
            mood_trend = "↗ Improving"
        elif morning_scores[-1] < morning_scores[0]:
            mood_trend = "↘ Declining"
        else:
            mood_trend = "→ Stable"
    else:
        mood_trend = "→ Stable"

    # Biggest win from extracted data
    all_wins = []
    for log in logs:
        for field in [log.morning_extracted, log.evening_extracted]:
            if field:
                all_wins.extend(field.get("wins", []))

    biggest_win = all_wins[0] if all_wins else "Showed up and logged."

    # Dominant life area
    all_areas = []
    for log in logs:
        for field in [log.morning_extracted, log.evening_extracted]:
            if field:
                all_areas.extend(field.get("life_areas_mentioned", []))

    from collections import Counter
    area_counter = Counter(all_areas)
    top_area = area_counter.most_common(1)[0][0] if area_counter else "general"

    # Streak
    streak = _calc_streak(db, user_id, today)

    # Week number
    week_num = today.isocalendar()[1]

    # AI persona generation
    week_summary = {
        "goal_completion": f"{completion_pct}%",
        "mood_trend": mood_trend,
        "best_day": best_day,
        "biggest_win": biggest_win,
        "top_area": top_area,
        "streak": streak,
        "total_goals_completed": completed,
        "total_goals_skipped": skipped,
    }

    try:
        persona_data = generate_weekly_persona(
            user_name=db.query(User).get(user_id).name,
            week_summary=week_summary,
            user_id=user_id,
        )
        persona_name = persona_data.get("persona_name", "The Evolving Self")
        coach_says = persona_data.get("coach_says", "Keep showing up.")
    except Exception:
        persona_name = "The Evolving Self"
        coach_says = "Keep showing up."

    return WeeklyCardOut(
        week_number=week_num,
        persona_name=persona_name,
        goal_completion=f"{completion_pct}%",
        mood_trend=mood_trend,
        best_day=best_day,
        biggest_win=biggest_win,
        life_area_highlight=top_area,
        coach_says=coach_says,
        streak=streak,
    )


# ─── DASHBOARD STATS ────────────────────────────────────────────
@router.get("/dashboard")
def get_dashboard_stats(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Consolidated dashboard data for the frontend."""
    today = datetime.today().date()
    seven_days_ago = today - timedelta(days=7)

    # Today's log status
    today_log = db.query(DailyLog).filter(
        DailyLog.user_id == user_id,
        DailyLog.log_date == today,
    ).first()

    # Streak
    streak = _calc_streak(db, user_id, today)

    # This week's goal completion
    week_goals = (
        db.query(DailyGoalLog)
        .filter(
            DailyGoalLog.user_id == user_id,
            DailyGoalLog.log_date >= seven_days_ago,
        )
        .all()
    )
    total = len(week_goals) or 1
    completed = sum(1 for gl in week_goals if gl.status == GoalLogStatus.completed)

    # Average mood this week
    week_logs = (
        db.query(DailyLog)
        .filter(DailyLog.user_id == user_id, DailyLog.log_date >= seven_days_ago)
        .all()
    )
    morning_scores = [l.morning_feeling_score for l in week_logs if l.morning_feeling_score]
    avg_mood = round(sum(morning_scores) / len(morning_scores), 1) if morning_scores else None

    # Latest advice
    latest_advice = (
        db.query(AIAdvice)
        .filter(AIAdvice.user_id == user_id)
        .order_by(AIAdvice.given_at.desc())
        .first()
    )

    # Active goals count
    active_goals = db.query(Goal).filter(
        Goal.user_id == user_id, Goal.is_active == True
    ).count()

    return {
        "streak": streak,
        "has_morning_log": bool(today_log and today_log.morning_text),
        "has_evening_log": bool(today_log and today_log.evening_text),
        "weekly_goal_completion": f"{round(completed/total*100)}%",
        "goals_completed_today": sum(
            1 for gl in week_goals
            if gl.log_date == today and gl.status == GoalLogStatus.completed
        ),
        "active_goals": active_goals,
        "avg_mood_7d": avg_mood,
        "latest_advice": latest_advice.advice_text[:150] if latest_advice else None,
        "latest_advice_at": str(latest_advice.given_at) if latest_advice else None,
    }


# ─── HELPERS ─────────────────────────────────────────────────────
def _calc_streak(db: Session, user_id: int, today) -> int:
    """Calculate consecutive days with at least one log entry."""
    streak = 0
    check_date = today

    for _ in range(365):
        log = db.query(DailyLog).filter(
            DailyLog.user_id == user_id,
            DailyLog.log_date == check_date,
        ).first()

        if log and (log.morning_text or log.evening_text):
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    return streak
