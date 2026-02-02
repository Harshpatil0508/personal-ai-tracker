from app.backgroundTask.celery_app import celery
from sqlalchemy import exists
from datetime import date
import logging
from app.database.database import SessionLocal
from app.database.models import DailyLog, User
logger = logging.getLogger(__name__)

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

            send_to_dead_letter.delay(
                user_id=user_id,
                source="auto_daily_log",
                error=str(e),
            )

            raise e

@celery.task
def send_to_dead_letter(user_id, source, error):
    logger.critical(
        f"[DLQ] {source} user={user_id} permanently failed → {error}"
    )

    # insert into dead_letter table
    # email
