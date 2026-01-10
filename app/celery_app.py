from celery import Celery
from celery.schedules import crontab
from app.config import REDIS_URL

celery = Celery(
    "personal_ai_tracker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks"],  # auto-discover tasks
)

# Timezone
celery.conf.timezone = "Asia/Kolkata"
celery.conf.enable_utc = False

# Celery Beat Schedules
celery.conf.beat_schedule = {
    "daily-job-every-midnight": {
        "task": "app.tasks.daily_job",
        "schedule": crontab(hour=0, minute=0),  # Every day 12:00 AM IST
    },
    "monthly-job-first-day": {
        "task": "app.tasks.monthly_job",
        "schedule": crontab(day_of_month=1, hour=1, minute=0),  # 1st day 1:00 AM IST
    },
}
