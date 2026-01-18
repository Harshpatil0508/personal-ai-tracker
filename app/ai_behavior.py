from sqlalchemy import text
from app.models import AIBehaviorProfile
from datetime import datetime, timezone


def update_behavior_profile(db, user_id: int):
    """
    Analyze past AI feedback and update user's behavior preferences.
    This runs offline (cron / celery beat), NOT during AI generation.
    """

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

    profile = db.get(AIBehaviorProfile, user_id)
    if not profile:
        profile = AIBehaviorProfile(user_id=user_id)

    profile.prefers_encouraging = encouraging_score >= 0
    profile.prefers_actionable = actionable_score >= 0
    profile.updated_at = datetime.now(timezone.utc)

    db.add(profile)
    db.commit()
