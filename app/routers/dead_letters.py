from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.database.models import DeadLetterTask
from app.dependencies import get_current_user_id
from app.database.models import User

router = APIRouter(prefix="/admin/dead-letter", tags=["Dead Letter Tasks"])


def require_admin(user_id: int, db: Session):
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/")
def list_failed_tasks(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
    limit: int = 20,
    offset: int = 0,
):
    require_admin(user_id, db)

    tasks = (
        db.query(DeadLetterTask)
        .order_by(DeadLetterTask.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    total = db.query(DeadLetterTask).count()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "tasks": tasks
    }


@router.get("/{task_id}")
def get_failed_task(
    task_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    require_admin(user_id, db)

    task = db.query(DeadLetterTask).filter(DeadLetterTask.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return task


@router.patch("/{task_id}/resolve")
def mark_task_resolved(
    task_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    require_admin(user_id, db)

    task = db.query(DeadLetterTask).filter(DeadLetterTask.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = "resolved"
    db.commit()

    return {"message": "Marked as resolved"}
