from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.database.models import AIValidation
from app.dependencies import get_current_user_id

router = APIRouter(prefix="/ai", tags=["AI Feedback"])
@router.get("/validation")
def get_ai_validation_results(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    return (
        db.query(AIValidation)
        .filter(AIValidation.user_id == user_id)
        .order_by(AIValidation.validated_at.desc())
        .all()
    )
