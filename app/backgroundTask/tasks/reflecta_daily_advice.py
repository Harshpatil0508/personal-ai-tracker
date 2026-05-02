"""
REFLECTA — Daily Advice Celery Task
Generates personalized coaching advice for all active users at 9 PM IST.
"""

import logging
from datetime import datetime, timedelta

from app.backgroundTask.celery_app import celery
from app.database.database import SessionLocal
from app.database.models import (
    User, UserOnboarding, DailyLog, Goal, DailyGoalLog,
    AIAdvice, PersonModel, GoalLogStatus, AdviceType,
)
from app.ai import generate_daily_advice
from app.services.rag_service import store_memory

logger = logging.getLogger(__name__)


@celery.task(name="app.backgroundTask.tasks.reflecta_daily_advice.daily_advice_dispatcher")
def daily_advice_dispatcher():
    """Dispatch daily advice generation for all active users."""
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.onboarding_complete == True).all()
        logger.info(f"[REFLECTA] Dispatching daily advice for {len(users)} users")

        for user in users:
            generate_advice_for_user.delay(user.id)

    except Exception as e:
        logger.error(f"[REFLECTA] Dispatcher error: {e}")
    finally:
        db.close()


@celery.task(
    name="app.backgroundTask.tasks.reflecta_daily_advice.generate_advice_for_user",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def generate_advice_for_user(self, user_id: int):
    """Generate daily advice for a single user."""
    db = SessionLocal()
    try:
        user = db.query(User).get(user_id)
        if not user:
            return

        # Gather all context
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
            "dominant_emotions": person.dominant_emotions,
        } if person else {}

        today = datetime.today().date()
        seven_days_ago = today - timedelta(days=7)

        # Recent logs
        recent_logs = (
            db.query(DailyLog)
            .filter(DailyLog.user_id == user_id, DailyLog.log_date >= seven_days_ago)
            .order_by(DailyLog.log_date.desc())
            .all()
        )

        # Mood trend
        mood_scores = [l.morning_feeling_score for l in recent_logs if l.morning_feeling_score]
        mood_trend = _calc_trend(mood_scores)

        # Stressors + excuses
        stressors, excuses = [], []
        for log in recent_logs:
            for field in [log.morning_extracted, log.evening_extracted]:
                if field:
                    stressors.extend(field.get("stressors", []))
                    excuses.extend(field.get("excuse_phrases", []))

        # Goal completion
        goals = db.query(Goal).filter(Goal.user_id == user_id, Goal.is_active == True).all()
        today_log = next((l for l in recent_logs if l.log_date == today), None)

        goal_logs = db.query(DailyGoalLog).filter(
            DailyGoalLog.user_id == user_id,
            DailyGoalLog.log_date >= seven_days_ago,
        ).all()
        weekly_completed = sum(1 for gl in goal_logs if gl.status == GoalLogStatus.completed)
        weekly_total = max(len(goal_logs), 1)
        completion_summary = f"{weekly_completed}/{weekly_total} ({round(weekly_completed/weekly_total*100)}%)"

        today_goals = [gl for gl in goal_logs if gl.log_date == today]
        completed_today = sum(1 for gl in today_goals if gl.status == GoalLogStatus.completed)

        days_active = (today - user.created_at.date()).days if user.created_at else 0

        # Generate
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

        # Save advice
        validate_at = datetime.now() + timedelta(days=14)
        advice = AIAdvice(
            user_id=user_id,
            advice_text=advice_text,
            advice_type=AdviceType.daily,
            validate_at=validate_at,
        )
        db.add(advice)

        # Store in memory
        try:
            store_memory(db, user_id, f"ADVICE: {advice_text}", "advice")
        except Exception:
            pass

        db.commit()
        logger.info(f"[REFLECTA] Daily advice generated for user {user_id}")

    except Exception as e:
        logger.error(f"[REFLECTA] Advice generation failed for user {user_id}: {e}")
        self.retry(exc=e)
    finally:
        db.close()


def _calc_trend(scores: list) -> str:
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
