"""
REFLECTA — Intervention Checker
Detects concerning patterns and triggers wellbeing interventions.
Called after every evening log submission.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.database.models import DailyLog

logger = logging.getLogger(__name__)

# ─── RULES ───────────────────────────────────────────────────────
# Each rule returns (triggered: bool, severity: str, message: str)

def check_mood_spiral(db: Session, user_id: int) -> tuple:
    """3+ consecutive days with morning_feeling_score <= 3"""
    three_days_ago = datetime.today().date() - timedelta(days=3)
    logs = (
        db.query(DailyLog)
        .filter(DailyLog.user_id == user_id, DailyLog.log_date >= three_days_ago)
        .order_by(DailyLog.log_date.desc())
        .all()
    )

    low_days = sum(
        1 for log in logs
        if log.morning_feeling_score and log.morning_feeling_score <= 3
    )

    if low_days >= 3:
        return (True, "high", "Your mood has been consistently low for 3+ days. This matters. Let's talk about what's going on.")

    return (False, "", "")


def check_concerning_language(db: Session, user_id: int) -> tuple:
    """Check today's extracted data for concerning phrases."""
    today = datetime.today().date()
    log = db.query(DailyLog).filter(
        DailyLog.user_id == user_id,
        DailyLog.log_date == today,
    ).first()

    if not log:
        return (False, "", "")

    concerning = []
    for field in [log.morning_extracted, log.evening_extracted]:
        if field:
            concerning.extend(field.get("concerning_phrases", []))

    if concerning:
        return (True, "critical", "I noticed some concerning language in your journal. Your wellbeing comes first — always.")

    return (False, "", "")


def check_zero_streak(db: Session, user_id: int) -> tuple:
    """5+ consecutive days with zero goals completed."""
    five_days_ago = datetime.today().date() - timedelta(days=5)
    from app.database.models import DailyGoalLog, GoalLogStatus

    recent_goals = (
        db.query(DailyGoalLog)
        .filter(
            DailyGoalLog.user_id == user_id,
            DailyGoalLog.log_date >= five_days_ago,
        )
        .all()
    )

    if not recent_goals:
        return (False, "", "")

    # Group by date
    by_date = {}
    for gl in recent_goals:
        by_date.setdefault(gl.log_date, []).append(gl)

    zero_days = sum(
        1 for date_logs in by_date.values()
        if all(gl.status != GoalLogStatus.completed for gl in date_logs)
    )

    if zero_days >= 5:
        return (True, "medium", "5 days without completing a single goal. Something is blocking you. Let's identify it.")

    return (False, "", "")


def check_high_energy_low_action(db: Session, user_id: int) -> tuple:
    """High intent score but consistently low completion — analysis paralysis."""
    three_days_ago = datetime.today().date() - timedelta(days=3)
    logs = (
        db.query(DailyLog)
        .filter(DailyLog.user_id == user_id, DailyLog.log_date >= three_days_ago)
        .all()
    )

    from app.database.models import DailyGoalLog, GoalLogStatus

    high_intent_low_action = 0
    for log in logs:
        intent = None
        for field in [log.morning_extracted, log.evening_extracted]:
            if field:
                intent = field.get("intent_score")
                break

        if intent and intent >= 7:
            day_goals = (
                db.query(DailyGoalLog)
                .filter(
                    DailyGoalLog.user_id == user_id,
                    DailyGoalLog.log_date == log.log_date,
                )
                .all()
            )
            if day_goals:
                completed = sum(1 for gl in day_goals if gl.status == GoalLogStatus.completed)
                if completed / len(day_goals) < 0.3:
                    high_intent_low_action += 1

    if high_intent_low_action >= 3:
        return (True, "medium", "You feel motivated but aren't following through. The gap between intention and action is where growth lives.")

    return (False, "", "")


# ─── MAIN CHECKER ────────────────────────────────────────────────
ALL_CHECKS = [
    check_concerning_language,
    check_mood_spiral,
    check_zero_streak,
    check_high_energy_low_action,
]

def run_intervention_checks(db: Session, user_id: int) -> list[dict]:
    """
    Run all intervention checks. Returns list of triggered interventions.
    Called after evening log submission.
    """
    interventions = []

    for check_fn in ALL_CHECKS:
        try:
            triggered, severity, message = check_fn(db, user_id)
            if triggered:
                interventions.append({
                    "check": check_fn.__name__,
                    "severity": severity,
                    "message": message,
                })
                logger.warning(
                    f"[INTERVENTION] {check_fn.__name__} triggered for user {user_id} "
                    f"(severity={severity})"
                )
        except Exception as e:
            logger.error(f"[INTERVENTION] {check_fn.__name__} error: {e}")

    return interventions
