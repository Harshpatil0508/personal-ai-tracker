from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.db import get_db
from app.dependencies import get_current_user_id
from app.models import AIFeedback
from app.schemas import AIFeedbackCreate

router = APIRouter(prefix="/ai", tags=["AI Feedback"])


@router.post("/feedback", status_code=status.HTTP_200_OK)
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

    updated = False

    if feedback:
        feedback.is_helpful = payload.is_helpful
        updated = True
    else:
        feedback = AIFeedback(
            user_id=user_id,
            source=payload.source,
            source_id=payload.source_id,
            is_helpful=payload.is_helpful,
        )
        db.add(feedback)

    try:
        db.commit()
        db.refresh(feedback)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to save AI feedback",
        )

    return {
        "status": "success",
        "updated": updated,
    }
