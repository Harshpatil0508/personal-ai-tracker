from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from collections import Counter

from app.dependencies import require_role
from app.database.db import get_db
from app.database.models import User, AIAdvice, PersonModel, DailyLog

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/dashboard")
def dashboard(user=Depends(require_role("admin"))):
    return {"message": "Welcome admin"}


@router.get("/metrics")
def get_success_metrics(db: Session = Depends(get_db)):
    """
    Get system-wide success metrics:
    - Average advice effectiveness score
    - Most common excuse patterns across ALL users
    - Day 1 -> Day 7 retention estimate
    - Total active users
    """
    total_users = db.query(User).count()

    avg_eff = db.query(func.avg(AIAdvice.effectiveness_score)).filter(
        AIAdvice.validated == True,
        AIAdvice.effectiveness_score.isnot(None)
    ).scalar()
    
    avg_effectiveness = round((avg_eff or 0) * 100, 1)

    all_models = db.query(PersonModel.top_excuses).filter(PersonModel.top_excuses.isnot(None)).all()
    all_excuses = []
    for model in all_models:
        if model[0]:
            all_excuses.extend(model[0])
            
    excuse_counter = Counter(all_excuses)
    top_excuses = [{"excuse": e, "count": c} for e, c in excuse_counter.most_common(10)]

    db_users = db.query(User).filter(User.created_at <= datetime.utcnow() - timedelta(days=7)).all()
    eligible_for_retention = len(db_users)
    retained_count = 0
    
    for u in db_users:
        if not u.created_at: continue
        day_7 = u.created_at.date() + timedelta(days=6)
        has_log = db.query(DailyLog).filter(DailyLog.user_id == u.id, DailyLog.log_date >= day_7).first()
        if has_log:
            retained_count += 1
            
    retention_rate = round((retained_count / eligible_for_retention * 100) if eligible_for_retention > 0 else 0, 1)

    return {
        "total_users": total_users,
        "metrics": {
            "average_advice_effectiveness_pct": avg_effectiveness,
            "day_7_retention_rate_pct": retention_rate,
            "intervention_frequency": "Not tracked natively yet"
        },
        "global_top_excuses": top_excuses
    }
