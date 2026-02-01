from celery import Celery
from celery.schedules import crontab
from app.config import REDIS_URL

celery = Celery(
    "personal_ai_tracker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.backgroundTask.tasks.daily_motivation",
        "app.backgroundTask.tasks.monthly_ai_review",
        "app.backgroundTask.tasks.auto_fill_logs",
        "app.backgroundTask.tasks.validate_daily_ai",
        "app.backgroundTask.tasks.validate_monthly_ai",
        "app.backgroundTask.tasks.weekly_behaviour",
        ],  # auto-discover tasks
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
    "daily-job-every-midnight": {
        "task": "app.backgroundTask.tasks.daily_motivation.daily_job_dispatcher",
        "schedule": crontab(hour=4, minute=0),  # Every day 4:00 AM IST
    },
    "monthly-job-first-day": {
        "task": "app.backgroundTask.tasks.monthly_ai_review.monthly_job_dispatcher",
        "schedule": crontab(day_of_month=1, hour=1, minute=0),  # 1st day 1:00 AM IST
    },
    "weekly-ai-behavior-profile": {
        "task": "app.backgroundTask.tasks.weekly_behaviour.weekly_behavior_profile_dispatcher",
        "schedule": crontab(day_of_week="sun", hour=2, minute=0),
    },
    "auto-daily-log":{
        "task": "app.backgroundTask.tasks.auto_fill_logs.auto_fill_daily_logs",
        "schedule": crontab(hour=3, minute=0),  # Every day 4:00 AM IST
    },
    "validate-daily-ai": {
        "task": "app.backgroundTask.tasks.validate_daily_ai.validate_daily_ai_dispatcher",
        "schedule": crontab(hour=3, minute=0),
    },
    "validate-monthly-ai": {
        "task": "app.backgroundTask.tasks.validate_monthly_ai.validate_monthly_ai_dispatcher",
        "schedule": crontab(day_of_month=15, hour=4, minute=0),
    },
}
