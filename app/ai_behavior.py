from sqlalchemy import text
from datetime import datetime, timezone
from app.database.models import AIBehaviorProfile, AIValidation


def update_behavior_profile(db, user_id: int):
    """
    Offline job.
    Combines:
    1) Explicit user feedback (likes/dislikes)
    2) Delayed validation (what actually worked)
    """

    # ---------- FEEDBACK LEARNING ----------
    rows = db.execute(text("""
        SELECT
            f.is_helpful,
            e.content
        FROM ai_feedback f
        JOIN ai_embeddings e
          ON e.user_id = f.user_id
         AND e.source = f.source
         AND e.source_id = f.source_id
        WHERE f.user_id = :user_id
    """), {"user_id": user_id}).fetchall()

    encouraging_score = 0
    actionable_score = 0

    for row in rows:
        text_content = row.content.lower()
        delta = 1 if row.is_helpful else -1

        if any(w in text_content for w in ["okay", "progress", "steady", "support"]):
            encouraging_score += delta

        if any(w in text_content for w in ["step", "plan", "do this", "action"]):
            actionable_score += delta

    # ---------- OUTCOME LEARNING ----------
    validations = (
        db.query(AIValidation)
        .filter(AIValidation.user_id == user_id)
        .all()
    )

    success_count = sum(1 for v in validations if v.result == "improved")
    failure_count = sum(1 for v in validations if v.result == "declined")

    # ---------- UPDATE PROFILE ----------
    profile = db.query(AIBehaviorProfile).filter_by(user_id=user_id).first()
    if not profile:
        profile = AIBehaviorProfile(user_id=user_id)

    profile.prefers_encouraging = encouraging_score >= 0
    profile.prefers_actionable = actionable_score >= 0
    profile.successful_advice = success_count
    profile.failed_advice = failure_count
    profile.updated_at = datetime.now(timezone.utc)

    db.add(profile)
    db.commit()
