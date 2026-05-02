"""
REFLECTA — Advice Validation Celery Task
Runs daily to check advice that has reached its validation window (14 days).
Compares before/after metrics to score effectiveness.
"""

import logging
from datetime import datetime, timedelta

from app.backgroundTask.celery_app import celery
from app.database.database import SessionLocal
from app.database.models import AIAdvice, DailyLog, DailyGoalLog, GoalLogStatus

logger = logging.getLogger(__name__)


@celery.task(name="app.backgroundTask.tasks.reflecta_validate_advice.validate_advice_dispatcher")
def validate_advice_dispatcher():
    """Find all advice due for validation and dispatch checks."""
    db = SessionLocal()
    try:
        now = datetime.now()
        due_advice = (
            db.query(AIAdvice)
            .filter(
                AIAdvice.validated == False,
                AIAdvice.validate_at <= now,
            )
            .all()
        )

        logger.info(f"[REFLECTA] Validating {len(due_advice)} advice records")

        for advice in due_advice:
            validate_single_advice.delay(advice.id)

    except Exception as e:
        logger.error(f"[REFLECTA] Validation dispatcher error: {e}")
    finally:
        db.close()


@celery.task(
    name="app.backgroundTask.tasks.reflecta_validate_advice.validate_single_advice",
    bind=True,
    max_retries=1,
)
def validate_single_advice(self, advice_id: int):
    """
    Validate a single piece of advice by comparing:
    - Mood trend before vs after the advice was given
    - Goal completion rate before vs after
    """
    db = SessionLocal()
    try:
        advice = db.query(AIAdvice).get(advice_id)
        if not advice or advice.validated:
            return

        user_id = advice.user_id
        advice_date = advice.given_at.date()

        # 7 days BEFORE the advice
        before_start = advice_date - timedelta(days=7)
        before_logs = (
            db.query(DailyLog)
            .filter(
                DailyLog.user_id == user_id,
                DailyLog.log_date >= before_start,
                DailyLog.log_date < advice_date,
            )
            .all()
        )

        # 7 days AFTER the advice
        after_end = advice_date + timedelta(days=14)
        after_logs = (
            db.query(DailyLog)
            .filter(
                DailyLog.user_id == user_id,
                DailyLog.log_date > advice_date,
                DailyLog.log_date <= after_end,
            )
            .all()
        )

        # Mood comparison
        before_moods = [l.morning_feeling_score for l in before_logs if l.morning_feeling_score]
        after_moods = [l.morning_feeling_score for l in after_logs if l.morning_feeling_score]

        before_mood_avg = sum(before_moods) / max(len(before_moods), 1) if before_moods else 5
        after_mood_avg = sum(after_moods) / max(len(after_moods), 1) if after_moods else 5

        # Goal completion comparison
        before_goals = (
            db.query(DailyGoalLog)
            .filter(
                DailyGoalLog.user_id == user_id,
                DailyGoalLog.log_date >= before_start,
                DailyGoalLog.log_date < advice_date,
            )
            .all()
        )
        after_goals = (
            db.query(DailyGoalLog)
            .filter(
                DailyGoalLog.user_id == user_id,
                DailyGoalLog.log_date > advice_date,
                DailyGoalLog.log_date <= after_end,
            )
            .all()
        )

        before_rate = (
            sum(1 for gl in before_goals if gl.status == GoalLogStatus.completed)
            / max(len(before_goals), 1)
        ) if before_goals else 0.5

        after_rate = (
            sum(1 for gl in after_goals if gl.status == GoalLogStatus.completed)
            / max(len(after_goals), 1)
        ) if after_goals else 0.5

        # Score: weighted combination of mood delta + completion delta
        mood_delta = after_mood_avg - before_mood_avg  # -10 to +10
        completion_delta = after_rate - before_rate  # -1 to +1

        # Normalize to 0-1 scale
        mood_score = max(0, min(1, (mood_delta + 5) / 10))
        completion_score = max(0, min(1, (completion_delta + 0.5)))

        effectiveness = round((mood_score * 0.4 + completion_score * 0.6), 3)

        # Outcome notes
        notes = []
        if mood_delta > 0.5:
            notes.append(f"Mood improved by {mood_delta:.1f}")
        elif mood_delta < -0.5:
            notes.append(f"Mood declined by {abs(mood_delta):.1f}")

        if completion_delta > 0.05:
            notes.append(f"Goal completion improved by {completion_delta*100:.0f}%")
        elif completion_delta < -0.05:
            notes.append(f"Goal completion dropped by {abs(completion_delta)*100:.0f}%")

        # Update advice record
        advice.validated = True
        advice.effectiveness_score = effectiveness
        advice.outcome_notes = "; ".join(notes) if notes else "No significant change detected"

        db.commit()
        logger.info(
            f"[REFLECTA] Advice {advice_id} validated: "
            f"effectiveness={effectiveness}, notes={advice.outcome_notes}"
        )

    except Exception as e:
        logger.error(f"[REFLECTA] Validation failed for advice {advice_id}: {e}")
        self.retry(exc=e)
    finally:
        db.close()
