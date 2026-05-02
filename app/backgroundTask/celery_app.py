"""
REFLECTA — Celery App Configuration
Scheduled jobs for daily advice, weekly person model, advice validation,
and goal auto-marking.
"""

from celery import Celery
from celery.schedules import crontab
from app.config import REDIS_URL

celery = Celery(
    "reflecta",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.backgroundTask.tasks.reflecta_daily_advice",
        "app.backgroundTask.tasks.reflecta_person_model",
        "app.backgroundTask.tasks.reflecta_validate_advice",
        "app.backgroundTask.tasks.reflecta_goal_automark",
        "app.backgroundTask.tasks.reflecta_monthly_report",
    ],
)

# Timezone
celery.conf.timezone = "Asia/Kolkata"
celery.conf.enable_utc = False
celery.conf.update(
    worker_concurrency=4,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

# Celery Beat Schedules
celery.conf.beat_schedule = {
    # Daily coaching advice at 9 PM IST
    "reflecta-daily-advice": {
        "task": "app.backgroundTask.tasks.reflecta_daily_advice.daily_advice_dispatcher",
        "schedule": crontab(hour=21, minute=0),
    },

    # Weekly person model rebuild — Sunday 8 PM IST
    "reflecta-person-model": {
        "task": "app.backgroundTask.tasks.reflecta_person_model.person_model_dispatcher",
        "schedule": crontab(day_of_week="sun", hour=20, minute=0),
    },

    # Advice validation — daily at 3 AM IST
    "reflecta-validate-advice": {
        "task": "app.backgroundTask.tasks.reflecta_validate_advice.validate_advice_dispatcher",
        "schedule": crontab(hour=3, minute=0),
    },

    # Auto-mark incomplete goals — midnight IST
    "reflecta-goal-automark": {
        "task": "app.backgroundTask.tasks.reflecta_goal_automark.mark_incomplete_goals",
        "schedule": crontab(hour=0, minute=5),
    },

    # Monthly narrative report — 1st of month, 7 AM IST
    "reflecta-monthly-report": {
        "task": "app.backgroundTask.tasks.reflecta_monthly_report.generate_monthly_reports_dispatcher",
        "schedule": crontab(day_of_month="1", hour=7, minute=0),
    },
}
