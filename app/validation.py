from datetime import timedelta, date
from app.database.database import SessionLocal
from app.database.models import DailyLog, AIValidation, AIBehaviorProfile


METRIC_WEIGHTS = {
    "mood_score": 1.0,
    "sleep_hours": 0.7,
    "work_hours": 0.5,
    "study_hours": 0.5,
    "goal_completed_percentage": 0.8,
}


def calculate_metric_average(db, user_id, metric, start_date, end_date):
    logs = (
        db.query(DailyLog)
        .filter(
            DailyLog.user_id == user_id,
            DailyLog.date >= start_date,
            DailyLog.date <= end_date,
            DailyLog.is_auto == False
        )
        .all()
    )

    values = [
        getattr(log, metric)
        for log in logs
        if getattr(log, metric) is not None
    ]

    if not values:
        return None

    return sum(values) / len(values)


def validate_ai_advice(
    user_id: int,
    ai_type: str,
    ai_ref_id: int,
    metric: str,
    days_window: int
):
    db = SessionLocal()
    today = date.today()

    # ---- Idempotency ----
    exists = (
        db.query(AIValidation)
        .filter_by(
            ai_type=ai_type,
            ai_ref_id=ai_ref_id,
            metric=metric
        )
        .first()
    )
    if exists:
        db.close()
        return

    # ---- Time windows ----
    before_start = today - timedelta(days=days_window * 2)
    before_end = today - timedelta(days=days_window)
    after_start = today - timedelta(days=days_window)
    after_end = today

    before_avg = calculate_metric_average(
        db, user_id, metric, before_start, before_end
    )
    after_avg = calculate_metric_average(
        db, user_id, metric, after_start, after_end
    )

    if before_avg is None or after_avg is None:
        db.close()
        return

    delta = after_avg - before_avg
    weight = METRIC_WEIGHTS.get(metric, 0.5)
    weighted_delta = delta * weight

    if weighted_delta > 0.5:
        result = "improved"
    elif weighted_delta < -0.5:
        result = "declined"
    else:
        result = "neutral"

    # ---- Store validation ----
    validation = AIValidation(
        user_id=user_id,
        ai_type=ai_type,
        ai_ref_id=ai_ref_id,
        metric=metric,
        before_value=round(before_avg, 2),
        after_value=round(after_avg, 2),
        delta=round(delta, 2),
        result=result,
    )

    db.add(validation)
    db.commit()

    # ---- UPDATE BEHAVIOR PROFILE ----
    profile = db.query(AIBehaviorProfile).filter_by(user_id=user_id).first()
    if not profile:
        profile = AIBehaviorProfile(user_id=user_id)
        db.add(profile)

    if result == "improved":
        profile.successful_advice += 1
    elif result == "declined":
        profile.failed_advice += 1

    db.commit()
    db.close()
