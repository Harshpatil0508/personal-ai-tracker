from datetime import timedelta
from app.database.database import SessionLocal
from app.database.models import DailyLog, AIValidation, AIBehaviorProfile


METRIC_WEIGHTS = {
    "mood_score": 1.0,
    "sleep_hours": 0.7,
    "work_hours": 0.5,
    "study_hours": 0.5,
    "goal_completed_percentage": 0.8,
}


def validate_ai_advice(
    user_id: int,
    ai_type: str,
    ai_ref_id: int,
    metric: str,
    days_window: int = 7
):
    db = SessionLocal()

    # ---------- IDEMPOTENCY ----------
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

    # ---------- FETCH ALL USER LOGS ----------
    logs = (
        db.query(DailyLog)
        .filter(
            DailyLog.user_id == user_id,
            DailyLog.is_auto == False
        )
        .order_by(DailyLog.date)
        .all()
    )

    # Require minimum history
    if len(logs) < 5:
        db.close()
        return

    # ---------- ADVICE REFERENCE DATE ----------
    advice_date = logs[-1].date
    first_log_date = logs[0].date
    available_days = (advice_date - first_log_date).days

    # Adaptive window
    window = min(days_window, max(available_days, 1))

    before_start = advice_date - timedelta(days=window)
    after_end = advice_date + timedelta(days=window)

    # ---------- BEFORE VALUES ----------
    before_values = [
        getattr(l, metric)
        for l in logs
        if (
            l.date >= before_start and
            l.date < advice_date and
            getattr(l, metric) is not None
        )
    ]

    # Fallback → first real log
    if not before_values:
        first_value = getattr(logs[0], metric)
        if first_value is None:
            db.close()
            return
        before_values = [first_value]

    # ---------- AFTER VALUES ----------
    after_values = [
        getattr(l, metric)
        for l in logs
        if (
            l.date > advice_date and
            l.date <= after_end and
            getattr(l, metric) is not None
        )
    ]

    if not after_values:
        db.close()
        return

    before_avg = sum(before_values) / len(before_values)
    after_avg = sum(after_values) / len(after_values)

    # ---------- WEIGHTED DELTA ----------
    delta = after_avg - before_avg
    weight = METRIC_WEIGHTS.get(metric, 0.5)
    weighted_delta = delta * weight

    if weighted_delta > 0.5:
        result = "improved"
    elif weighted_delta < -0.5:
        result = "declined"
    else:
        result = "neutral"

    # ---------- STORE VALIDATION ----------
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

    # ---------- UPDATE BEHAVIOR PROFILE ----------
    profile = (
        db.query(AIBehaviorProfile)
        .filter_by(user_id=user_id)
        .first()
    )

    if not profile:
        profile = AIBehaviorProfile(
            user_id=user_id,
            successful_advice=0,
            failed_advice=0
        )
        db.add(profile)

    if result == "improved":
        profile.successful_advice += 1
    elif result == "declined":
        profile.failed_advice += 1

    db.commit()
    db.close()
