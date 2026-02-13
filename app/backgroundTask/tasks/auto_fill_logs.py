from app.backgroundTask.celery_app import celery
from sqlalchemy import exists
from datetime import date, datetime, timezone
import logging
from app.database.database import SessionLocal
from app.database.models import DailyLog, DeadLetterTask, User
from celery import Task
logger = logging.getLogger(__name__)


class AutoLogsTask(Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        user_id = args[0]

        logger.critical(
            f"[USER AUTO FILL LOGS JOB] FINAL FAILURE user={user_id} task_id={task_id} error={exc}"
        )

        send_to_dead_letter.delay(
            user_id=user_id,
            source="auto_daily_log",
            error=str(exc),
        )

@celery.task(bind=True,autoretry_for=(Exception,), retry_kwargs={"max_retries": 3, "countdown": 60})
def auto_fill_daily_logs(self):
    """
    Creates a default DailyLog for users who did not add one today.
    Marks it as system-generated (is_auto=True).
    """
    today = date.today()
    logger.info(f"[AUTO LOG JOB] Starting auto-fill for {today}")

    with SessionLocal() as db:
        users = db.query(User.id).all()

    for (user_id,) in users:
        process_user_auto_daily_log.delay(user_id, today)

    logger.info("[AUTO LOG JOB] Completed auto-fill job")

@celery.task(
    bind=True,
    base=AutoLogsTask,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,   # up to 10 minutes
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def process_user_auto_daily_log(self, user_id: int, today: date):

    logger.info(f"[AUTO LOG USER] Start user={user_id}")

    with SessionLocal() as db:
        try:
            raise Exception("test failure")
            exists_today = (
                db.query(DailyLog)
                .filter(
                    DailyLog.user_id == user_id,
                    DailyLog.date == today,
                )
                .first()
            )

            if exists_today:
                logger.info(
                    f"[AUTO LOG USER] Exists user={user_id}, skipping"
                )
                return

            auto_log = DailyLog(
                user_id=user_id,
                date=today,
                work_hours=0.0,
                study_hours=0.0,
                sleep_hours=None,
                mood_score=None,
                goal_completed_percentage=0.0,
                notes="Auto-generated: no entry for this day",
                is_auto=True,
            )

            db.add(auto_log)
            db.commit()

            logger.info(
                f"[AUTO LOG USER] Created auto log user={user_id}"
            )

        except Exception as e:
            db.rollback()

            logger.exception(
                f"[AUTO LOG USER] HARD FAIL user={user_id}"
            )
            raise 

@celery.task
def send_to_dead_letter(user_id: int, source: str, error: str):
    """
    Stores failed Celery tasks into DB for monitoring + debugging.
    """

    logger.critical(f"[DLQ] source={source} user={user_id} error={error}")

    with SessionLocal() as db:
        dlq = DeadLetterTask(
            user_id=user_id,
            source=source,
            error=error,
            status="failed",
            created_at=datetime.now(timezone.utc),
        )

        db.add(dlq)
        db.commit()

