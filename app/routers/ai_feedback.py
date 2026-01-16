from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.dependencies import get_current_user_id
from app.models import AIFeedback, User
from app.schemas import AIFeedbackCreate

router = APIRouter(prefix="/ai", tags=["AI Feedback"])

@router.post("/feedback")
def submit_ai_feedback(
    payload: AIFeedbackCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    feedback = (
        db.query(AIFeedback)
        .filter(
            AIFeedback.user_id == user_id,
            AIFeedback.source == payload.source,
            AIFeedback.source_id == payload.source_id,
        )
        .first()
    )

    if feedback:
        # allow update (user can change mind)
        feedback.is_helpful = payload.is_helpful
    else:
        feedback = AIFeedback(
            user_id=user_id,
            source=payload.source,
            source_id=payload.source_id,
            is_helpful=payload.is_helpful,
        )
        db.add(feedback)

    db.commit()
    return {"status": "ok"}
