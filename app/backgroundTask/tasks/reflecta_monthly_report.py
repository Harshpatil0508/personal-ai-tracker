import logging
from datetime import datetime, timedelta
import collections

from celery import shared_task

from app.database.database import SessionLocal
from app.database.models import User, Goal, DailyGoalLog, DailyLog, AIAdvice, GoalLogStatus, AdviceType, PersonModel
from app.ai import generate_monthly_report

logger = logging.getLogger(__name__)

@shared_task(name="reflecta.monthly_report")
def generate_monthly_reports_dispatcher():
    """Run monthly narrative report for all active users."""
    logger.info("[CELERY START] Generating monthly reports for all users...")
    
    with SessionLocal() as db:
        users = db.query(User).filter(User.onboarding_complete == True).all()
        for user in users: # Add some simple check if user was active recently
            try:
                generate_report_for_user(user.id)
            except Exception as e:
                logger.error(f"[CELERY ERROR] User {user.id} monthly report: {e}")

def generate_report_for_user(user_id: int):
    with SessionLocal() as db:
        user = db.query(User).get(user_id)
        if not user:
            return

        today = datetime.today().date()
        thirty_days_ago = today - timedelta(days=30)
        month_name = thirty_days_ago.strftime("%B")

        # Gather data
        logs = db.query(DailyLog).filter(DailyLog.user_id == user_id, DailyLog.log_date >= thirty_days_ago).all()
        active_days = len(logs)
        if active_days == 0:
            return

        goals = db.query(Goal).filter(Goal.user_id == user_id).all()
        goal_logs = db.query(DailyGoalLog).filter(DailyGoalLog.user_id == user_id, DailyGoalLog.log_date >= thirty_days_ago).all()
        
        total_goal_attempts = len(goal_logs)
        completed_goals = sum(1 for gl in goal_logs if gl.status == GoalLogStatus.completed)
        completion_rate = round((completed_goals / total_goal_attempts * 100) if total_goal_attempts else 0, 1)

        # Best/Worst category
        cat_stats = collections.defaultdict(lambda: {"total": 0, "completed": 0})
        for gl in goal_logs:
            g = db.query(Goal).get(gl.goal_id)
            if g:
                cat = g.category.value if hasattr(g.category, 'value') else g.category
                cat_stats[cat]["total"] += 1
                if gl.status == GoalLogStatus.completed:
                    cat_stats[cat]["completed"] += 1

        cat_rates = {cat: round(s["completed"]/s["total"]*100) for cat, s in cat_stats.items() if s["total"] > 0}
        best_category = max(cat_rates.items(), key=lambda x: x[1])[0] if cat_rates else "N/A"
        best_rate = cat_rates.get(best_category, 0)
        worst_category = min(cat_rates.items(), key=lambda x: x[1])[0] if cat_rates else "N/A"
        worst_rate = cat_rates.get(worst_category, 0)

        # Advice effectiveness
        advices = db.query(AIAdvice).filter(AIAdvice.user_id == user_id, AIAdvice.validated == True, AIAdvice.given_at >= thirty_days_ago).all()
        if advices:
            advice_eff = sum(a.effectiveness_score or 0 for a in advices) / len(advices) * 100
        else:
            advice_eff = 0.0

        # Person model
        person = db.query(PersonModel).filter_by(user_id=user_id).first()
        top_excuse = "N/A"
        if person and person.top_excuses and len(person.top_excuses) > 0:
            top_excuse = person.top_excuses[0]
            
        emotion_summary = person.dominant_emotions if person else {}
        model_delta = {"consistency": person.consistency_style if person else "N/A"}

        # Wins and mood trend
        all_wins = []
        morning_scores = []
        for log in logs:
            if log.morning_feeling_score: morning_scores.append(log.morning_feeling_score)
            if log.evening_extracted and "wins" in log.evening_extracted:
                all_wins.extend(log.evening_extracted["wins"])
                
        biggest_win = all_wins[0] if all_wins else "Showing up"
        mood_direction = "Stable"
        if len(morning_scores) >= 2:
            mood_direction = "Improving" if morning_scores[-1] > morning_scores[0] else "Declining"

        tone = user.coach_tone.value if hasattr(user.coach_tone, 'value') else user.coach_tone

        # Generate report
        report_text = generate_monthly_report(
            user_name=user.name,
            coach_tone=tone,
            month_name=month_name,
            active_days=active_days,
            completion_rate=completion_rate,
            best_category=best_category,
            best_rate=best_rate,
            worst_category=worst_category,
            worst_rate=worst_rate,
            emotion_summary=emotion_summary,
            top_excuse=top_excuse,
            biggest_win=biggest_win,
            mood_direction=mood_direction,
            advice_effectiveness=round(advice_eff, 1),
            model_delta=model_delta,
            user_id=user.id
        )

        # Save as monthly advice
        advice_record = AIAdvice(
            user_id=user_id,
            advice_text=report_text,
            advice_type=AdviceType.monthly,
            validate_at=datetime.now() + timedelta(days=30),  # Not strictly validating monthly, but giving it a future date
        )
        db.add(advice_record)
        db.commit()
        logger.info(f"[REFLECTA] Monthly report saved for User {user_id}")
