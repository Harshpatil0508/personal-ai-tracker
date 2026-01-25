from celery import Celery
from celery.schedules import crontab
from app.config import REDIS_URL

celery = Celery(
    "personal_ai_tracker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.backgroundTask.tasks"],  # auto-discover tasks
)

# Timezone
celery.conf.timezone = "Asia/Kolkata"
celery.conf.enable_utc = False

# Celery Beat Schedules
celery.conf.beat_schedule = {
    "daily-job-every-midnight": {
        "task": "app.backgroundTask.tasks.daily_job",
        "schedule": crontab(hour=4, minute=0),  # Every day 4:00 AM IST
    },
    "monthly-job-first-day": {
        "task": "app.backgroundTask.tasks.monthly_job",
        "schedule": crontab(day_of_month=1, hour=1, minute=0),  # 1st day 1:00 AM IST
    },
    "weekly-ai-behavior-profile": {
        "task": "app.backgroundTask.tasks.behavior_job.weekly_behavior_profile_job",
        "schedule": crontab(day_of_week="sun", hour=2, minute=0),
    },
    "auto-daily-log":{
        "task": "app.backgroundTask.tasks.auto_daily_log_job",
        "schedule": crontab(hour=3, minute=0),  # Every day 4:00 AM IST
    },
    "validate-daily-ai": {
        "task": "app.backgroundTask.tasks.validate_daily_ai",
        "schedule": crontab(hour=3, minute=0),
    },
    "validate-monthly-ai": {
        "task": "app.backgroundTask.tasks.validate_monthly_ai",
        "schedule": crontab(day_of_month=15, hour=4, minute=0),
    },
}
