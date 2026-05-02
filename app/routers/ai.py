"""
REFLECTA — AI Router
Endpoints for daily advice, weekly patterns, monthly reports,
person model, excuse patterns, and advice validation.
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
from app.schemas import AIAdviceOut, PersonModelOut, AdviceValidationOut
from app.dependencies import get_current_user_id
from app.database.db import get_db
from app.ai import generate_daily_advice, generate_monthly_report, analyze_excuse_patterns

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["AI Coach"])


# ─── DAILY ADVICE ────────────────────────────────────────────────
@router.get("/daily-advice")
def get_daily_advice(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Generate and return today's AI coaching advice."""

    user = db.query(User).get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Gather context
    onboarding = db.query(UserOnboarding).filter_by(user_id=user_id).first()
    onboarding_data = {
        "life_area_focus": onboarding.life_area_focus,
        "past_failures": onboarding.past_failures,
        "biggest_excuse": onboarding.biggest_excuse,
        "life_scores": onboarding.life_scores,
    } if onboarding else {}

    person = db.query(PersonModel).filter_by(user_id=user_id).first()
    person_data = {
        "top_excuses": person.top_excuses,
        "consistency_style": person.consistency_style,
        "peak_performance_days": person.peak_performance_days,
        "goal_dna": person.goal_dna,
        "life_area_scores": person.life_area_scores,
        "dominant_emotions": person.dominant_emotions,
    } if person else {}

    # Last 7 days data
    seven_days_ago = datetime.today().date() - timedelta(days=7)
    recent_logs = (
        db.query(DailyLog)
        .filter(DailyLog.user_id == user_id, DailyLog.log_date >= seven_days_ago)
        .order_by(DailyLog.log_date.desc())
        .all()
    )

    # Mood trend
    mood_scores = [l.morning_feeling_score for l in recent_logs if l.morning_feeling_score]
    mood_trend = _calc_trend(mood_scores) if mood_scores else "insufficient data"

    # Stressors and excuses from extracted data
    stressors = []
    excuses = []
    for log in recent_logs:
        if log.morning_extracted:
            stressors.extend(log.morning_extracted.get("stressors", []))
            excuses.extend(log.morning_extracted.get("excuse_phrases", []))
        if log.evening_extracted:
            stressors.extend(log.evening_extracted.get("stressors", []))
            excuses.extend(log.evening_extracted.get("excuse_phrases", []))

    # Goal completion summary
    goals = db.query(Goal).filter(Goal.user_id == user_id, Goal.is_active == True).all()
    today = datetime.today().date()
    goal_logs_today = db.query(DailyGoalLog).filter(
        DailyGoalLog.user_id == user_id,
        DailyGoalLog.log_date == today,
    ).all()
    completed_today = sum(1 for gl in goal_logs_today if gl.status == GoalLogStatus.completed)

    # Weekly completion
    weekly_goal_logs = db.query(DailyGoalLog).filter(
        DailyGoalLog.user_id == user_id,
        DailyGoalLog.log_date >= seven_days_ago,
    ).all()
    weekly_completed = sum(1 for gl in weekly_goal_logs if gl.status == GoalLogStatus.completed)
    weekly_total = len(weekly_goal_logs) or 1
    completion_summary = f"{weekly_completed}/{weekly_total} ({round(weekly_completed/weekly_total*100)}%)"

    # Today's log
    today_log = next((l for l in recent_logs if l.log_date == today), None)

    # Days active
    days_active = (today - user.created_at.date()).days if user.created_at else 0

    # Generate advice
    advice_text = generate_daily_advice(
        user_name=user.name,
        coach_tone=user.coach_tone.value if hasattr(user.coach_tone, 'value') else user.coach_tone,
        days_active=days_active,
        onboarding_data=onboarding_data,
        person_model_data=person_data,
        completion_summary=completion_summary,
        mood_trend=mood_trend,
        stressors=list(set(stressors))[:5],
        excuses=list(set(excuses))[:5],
        morning_score=today_log.morning_feeling_score if today_log else None,
        morning_text=today_log.morning_text if today_log else None,
        evening_text=today_log.evening_text if today_log else None,
        goals_completed=completed_today,
        goals_total=len(goals),
        user_id=user_id,
    )

    # Save to ai_advice table
    validate_at = datetime.now() + timedelta(days=14)
    advice_record = AIAdvice(
        user_id=user_id,
        advice_text=advice_text,
        advice_type=AdviceType.daily,
        validate_at=validate_at,
    )
    db.add(advice_record)
    db.commit()
    db.refresh(advice_record)

    return {
        "advice": advice_text,
        "advice_id": advice_record.id,
        "mood_trend": mood_trend,
        "goals_today": f"{completed_today}/{len(goals)}",
    }


# ─── PERSON MODEL ───────────────────────────────────────────────
@router.get("/person-model", response_model=PersonModelOut)
def get_person_model(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get the current person model for the user."""
    person = db.query(PersonModel).filter_by(user_id=user_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person model not built yet. Keep logging for a week!")
    return person


# ─── EXCUSE PATTERNS ────────────────────────────────────────────
@router.get("/excuse-patterns")
def get_excuse_patterns(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Analyze and return recurring excuse patterns."""
    user = db.query(User).get(user_id)

    thirty_days_ago = datetime.today().date() - timedelta(days=30)
    logs = (
        db.query(DailyLog)
        .filter(DailyLog.user_id == user_id, DailyLog.log_date >= thirty_days_ago)
        .all()
    )

    excuses = []
    for log in logs:
        if log.morning_extracted:
            excuses.extend(log.morning_extracted.get("excuse_phrases", []))
        if log.evening_extracted:
            excuses.extend(log.evening_extracted.get("excuse_phrases", []))

    # Also get skip reasons from goal logs
    skip_reasons = (
        db.query(DailyGoalLog.skip_reason)
        .filter(
            DailyGoalLog.user_id == user_id,
            DailyGoalLog.log_date >= thirty_days_ago,
            DailyGoalLog.skip_reason.isnot(None),
        )
        .all()
    )
    excuses.extend([r[0] for r in skip_reasons if r[0]])

    if not excuses:
        return {"patterns": [], "message": "No excuse patterns detected yet."}

    return analyze_excuse_patterns(user.name, excuses, user_id)


# ─── ADVICE VALIDATION ──────────────────────────────────────────
@router.get("/advice-validation", response_model=list[AdviceValidationOut])
def get_advice_validation(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Show which past advice worked and which didn't."""
    advice_list = (
        db.query(AIAdvice)
        .filter(AIAdvice.user_id == user_id, AIAdvice.validated == True)
        .order_by(AIAdvice.given_at.desc())
        .limit(20)
        .all()
    )
    return advice_list


# ─── ADVICE HISTORY ──────────────────────────────────────────────
@router.get("/advice-history", response_model=list[AIAdviceOut])
def get_advice_history(
    days: int = 30,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get recent AI advice history."""
    start_date = datetime.today() - timedelta(days=days)
    advice_list = (
        db.query(AIAdvice)
        .filter(AIAdvice.user_id == user_id, AIAdvice.given_at >= start_date)
        .order_by(AIAdvice.given_at.desc())
        .all()
    )
    return advice_list


# ─── MONTHLY REPORT ──────────────────────────────────────────────
@router.get("/monthly-report")
def get_monthly_report(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get the latest generated monthly narrative report."""
    report = (
        db.query(AIAdvice)
        .filter(AIAdvice.user_id == user_id, AIAdvice.advice_type == AdviceType.monthly)
        .order_by(AIAdvice.given_at.desc())
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="No monthly report generated yet.")
    
    return {"month_report": report.advice_text, "generated_at": report.given_at}


# ─── WEEKLY PATTERNS ─────────────────────────────────────────────
@router.get("/weekly-patterns")
def get_weekly_patterns(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get weekly pattern analysis (proxying the analytics weekly card)."""
    from app.routers.analytics import get_weekly_card
    return get_weekly_card(user_id=user_id, db=db)


# ─── HELPERS ─────────────────────────────────────────────────────
def _calc_trend(scores: list) -> str:
    """Calculate mood trend from a list of scores."""
    if len(scores) < 2:
        return "stable"
    first_half = sum(scores[len(scores)//2:]) / max(len(scores)//2, 1)
    second_half = sum(scores[:len(scores)//2]) / max(len(scores)//2, 1)
    diff = second_half - first_half
    if diff > 1:
        return "improving"
    elif diff < -1:
        return "declining"
    return "stable"
