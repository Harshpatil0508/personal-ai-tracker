"""
REFLECTA — Goal Auto-Mark Celery Task
Runs at midnight to mark all unchecked goals as 'incomplete' for the day.
"""

import logging
from datetime import datetime

from app.backgroundTask.celery_app import celery
from app.database.database import SessionLocal
from app.database.models import Goal, DailyGoalLog, GoalLogStatus

logger = logging.getLogger(__name__)


@celery.task(name="app.backgroundTask.tasks.reflecta_goal_automark.mark_incomplete_goals")
def mark_incomplete_goals():
    """
    At midnight, mark all active goals that weren't completed or skipped
    as 'incomplete' for the previous day.
    """
    db = SessionLocal()
    try:
        yesterday = datetime.today().date()

        # Get all active goals grouped by user
        active_goals = db.query(Goal).filter(Goal.is_active == True).all()

        created = 0
        for goal in active_goals:
            # Check if a log already exists for this goal today
            existing = (
                db.query(DailyGoalLog)
                .filter_by(goal_id=goal.id, log_date=yesterday)
                .first()
            )

            if not existing:
                log = DailyGoalLog(
                    goal_id=goal.id,
                    user_id=goal.user_id,
                    log_date=yesterday,
                    status=GoalLogStatus.incomplete,
                )
                db.add(log)
                created += 1

        db.commit()
        logger.info(f"[REFLECTA] Auto-marked {created} goals as incomplete for {yesterday}")

    except Exception as e:
        logger.error(f"[REFLECTA] Goal auto-mark error: {e}")
    finally:
        db.close()
