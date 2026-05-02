"""
REFLECTA — Goals Router
Goal CRUD + daily status tracking (completed/skipped/incomplete).
"""

import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.models import Goal, DailyGoalLog, GoalLogStatus
from app.schemas import GoalCreate, GoalOut, GoalSkipRequest, GoalConsistencyOut
from app.dependencies import get_current_user_id
from app.database.db import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/goals", tags=["Goals"])


# ─── CREATE GOAL ─────────────────────────────────────────────────
@router.post("/", response_model=GoalOut, status_code=201)
def create_goal(
    data: GoalCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Create a new goal."""
    goal = Goal(
        user_id=user_id,
        title=data.title,
        category=data.category,
        target_date=data.target_date,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


# ─── GET ACTIVE GOALS ───────────────────────────────────────────
@router.get("/", response_model=list[GoalOut])
def get_active_goals(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get all active goals for the current user."""
    goals = (
        db.query(Goal)
        .filter(Goal.user_id == user_id, Goal.is_active == True)
        .order_by(Goal.created_date.desc())
        .all()
    )
    return goals


# ─── GET ALL GOALS (including inactive) ──────────────────────────
@router.get("/all", response_model=list[GoalOut])
def get_all_goals(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get all goals (active + inactive)."""
    goals = (
        db.query(Goal)
        .filter(Goal.user_id == user_id)
        .order_by(Goal.created_date.desc())
        .all()
    )
    return goals


# ─── MARK GOAL COMPLETE FOR TODAY ────────────────────────────────
@router.patch("/{goal_id}/complete")
def complete_goal_today(
    goal_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Mark a goal as completed for today."""
    goal = _get_user_goal(db, goal_id, user_id)
    today = datetime.today().date()

    # Check if already logged today
    existing = db.query(DailyGoalLog).filter_by(
        goal_id=goal_id, log_date=today,
    ).first()

    if existing:
        existing.status = GoalLogStatus.completed
        existing.skip_reason = None
    else:
        log = DailyGoalLog(
            goal_id=goal_id,
            user_id=user_id,
            log_date=today,
            status=GoalLogStatus.completed,
        )
        db.add(log)

    db.commit()
    return {"message": f"Goal '{goal.title}' marked as complete for today"}


# ─── MARK GOAL SKIPPED FOR TODAY ────────────────────────────────
@router.patch("/{goal_id}/skip")
def skip_goal_today(
    goal_id: int,
    data: GoalSkipRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Mark a goal as skipped for today (captures reason silently)."""
    goal = _get_user_goal(db, goal_id, user_id)
    today = datetime.today().date()

    existing = db.query(DailyGoalLog).filter_by(
        goal_id=goal_id, log_date=today,
    ).first()

    if existing:
        existing.status = GoalLogStatus.skipped
        existing.skip_reason = data.skip_reason
    else:
        log = DailyGoalLog(
            goal_id=goal_id,
            user_id=user_id,
            log_date=today,
            status=GoalLogStatus.skipped,
            skip_reason=data.skip_reason,
        )
        db.add(log)

    db.commit()
    return {"message": f"Goal '{goal.title}' marked as skipped", "reason": data.skip_reason}


# ─── DEACTIVATE GOAL ────────────────────────────────────────────
@router.patch("/{goal_id}/deactivate")
def deactivate_goal(
    goal_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Deactivate a goal (soft delete)."""
    goal = _get_user_goal(db, goal_id, user_id)
    goal.is_active = False
    db.commit()
    return {"message": f"Goal '{goal.title}' deactivated"}


# ─── GOAL CONSISTENCY ───────────────────────────────────────────
@router.get("/consistency", response_model=list[GoalConsistencyOut])
def get_goal_consistency(
    days: int = 30,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Get completion consistency stats for each active goal.
    Shows completed/skipped/incomplete counts over the specified window.
    """
    goals = (
        db.query(Goal)
        .filter(Goal.user_id == user_id, Goal.is_active == True)
        .all()
    )

    start_date = datetime.today().date() - timedelta(days=days)
    results = []

    for goal in goals:
        logs = (
            db.query(DailyGoalLog)
            .filter(
                DailyGoalLog.goal_id == goal.id,
                DailyGoalLog.log_date >= start_date,
            )
            .all()
        )

        completed = sum(1 for l in logs if l.status == GoalLogStatus.completed)
        skipped   = sum(1 for l in logs if l.status == GoalLogStatus.skipped)
        incomplete = sum(1 for l in logs if l.status == GoalLogStatus.incomplete)
        total = max(len(logs), 1)

        results.append(GoalConsistencyOut(
            goal_id=goal.id,
            title=goal.title,
            category=goal.category.value if hasattr(goal.category, 'value') else goal.category,
            total_days=len(logs),
            completed_days=completed,
            skipped_days=skipped,
            incomplete_days=incomplete,
            completion_rate=round((completed / total) * 100, 1),
        ))

    return results


# ─── GET TODAY'S GOAL STATUS ─────────────────────────────────────
@router.get("/today")
def get_today_goal_status(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get all active goals with today's completion status."""
    today = datetime.today().date()
    goals = (
        db.query(Goal)
        .filter(Goal.user_id == user_id, Goal.is_active == True)
        .all()
    )

    result = []
    for goal in goals:
        today_log = (
            db.query(DailyGoalLog)
            .filter_by(goal_id=goal.id, log_date=today)
            .first()
        )

        result.append({
            "id": goal.id,
            "title": goal.title,
            "category": goal.category.value if hasattr(goal.category, 'value') else goal.category,
            "status": today_log.status.value if today_log else "pending",
            "skip_reason": today_log.skip_reason if today_log else None,
        })

    return result


# ─── HELPER ──────────────────────────────────────────────────────
def _get_user_goal(db: Session, goal_id: int, user_id: int) -> Goal:
    """Fetch a goal belonging to the user or raise 404."""
    goal = db.query(Goal).filter(Goal.id == goal_id, Goal.user_id == user_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal
