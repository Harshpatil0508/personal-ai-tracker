"""
REFLECTA — Person Model Builder (Weekly Celery Task)
Rebuilds the user's behavioral archetype every Sunday at 8 PM IST.
Analyzes 30 days of data to identify:
- Top excuses
- Consistency style
- Peak performance days
- Goal DNA (completion rates per category)
- Dominant emotions
- Mood-performance correlation
"""

import logging
from datetime import datetime, timedelta
from collections import Counter

from app.backgroundTask.celery_app import celery
from app.database.database import SessionLocal
from app.database.models import (
    User, DailyLog, Goal, DailyGoalLog,
    PersonModel, GoalLogStatus,
)

logger = logging.getLogger(__name__)


@celery.task(name="app.backgroundTask.tasks.reflecta_person_model.person_model_dispatcher")
def person_model_dispatcher():
    """Dispatch person model update for all active users."""
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.onboarding_complete == True).all()
        logger.info(f"[REFLECTA] Building person models for {len(users)} users")

        for user in users:
            build_person_model.delay(user.id)

    except Exception as e:
        logger.error(f"[REFLECTA] Person model dispatcher error: {e}")
    finally:
        db.close()


@celery.task(
    name="app.backgroundTask.tasks.reflecta_person_model.build_person_model",
    bind=True,
    max_retries=1,
)
def build_person_model(self, user_id: int):
    """Build or update the person model from 30 days of data."""
    db = SessionLocal()
    try:
        today = datetime.today().date()
        thirty_days_ago = today - timedelta(days=30)

        # ─── COLLECT DATA ────────────────────────────────────────
        logs = (
            db.query(DailyLog)
            .filter(DailyLog.user_id == user_id, DailyLog.log_date >= thirty_days_ago)
            .all()
        )

        goal_logs = (
            db.query(DailyGoalLog)
            .filter(DailyGoalLog.user_id == user_id, DailyGoalLog.log_date >= thirty_days_ago)
            .all()
        )

        goals = db.query(Goal).filter(Goal.user_id == user_id).all()

        if len(logs) < 3:
            logger.info(f"[REFLECTA] Insufficient data for user {user_id} ({len(logs)} logs)")
            return

        # ─── TOP EXCUSES ─────────────────────────────────────────
        all_excuses = []
        for log in logs:
            for field in [log.morning_extracted, log.evening_extracted]:
                if field:
                    all_excuses.extend(field.get("excuse_phrases", []))

        # Add skip reasons
        for gl in goal_logs:
            if gl.skip_reason:
                all_excuses.append(gl.skip_reason)

        excuse_counter = Counter(all_excuses)
        top_excuses = [e for e, _ in excuse_counter.most_common(5)]

        # ─── CONSISTENCY STYLE ───────────────────────────────────
        total_gl = len(goal_logs)
        completed_gl = sum(1 for gl in goal_logs if gl.status == GoalLogStatus.completed)

        if total_gl == 0:
            consistency_style = "unknown"
        else:
            rate = completed_gl / total_gl
            if rate >= 0.85:
                consistency_style = "machine"
            elif rate >= 0.65:
                consistency_style = "steady"
            elif rate >= 0.4:
                consistency_style = "streaky"
            else:
                consistency_style = "struggling"

        # ─── PEAK PERFORMANCE DAYS ───────────────────────────────
        day_performance = {}
        for gl in goal_logs:
            day_name = gl.log_date.strftime("%A")
            if day_name not in day_performance:
                day_performance[day_name] = {"completed": 0, "total": 0}
            day_performance[day_name]["total"] += 1
            if gl.status == GoalLogStatus.completed:
                day_performance[day_name]["completed"] += 1

        peak_days = sorted(
            day_performance.items(),
            key=lambda x: x[1]["completed"] / max(x[1]["total"], 1),
            reverse=True,
        )
        peak_performance_days = [d[0] for d in peak_days[:3]]

        # ─── GOAL DNA (completion rate per category) ─────────────
        goal_map = {g.id: g for g in goals}
        category_stats = {}
        for gl in goal_logs:
            goal = goal_map.get(gl.goal_id)
            if not goal:
                continue
            cat = goal.category.value if hasattr(goal.category, 'value') else goal.category
            if cat not in category_stats:
                category_stats[cat] = {"completed": 0, "total": 0}
            category_stats[cat]["total"] += 1
            if gl.status == GoalLogStatus.completed:
                category_stats[cat]["completed"] += 1

        goal_dna = {
            cat: round(s["completed"] / max(s["total"], 1) * 100, 1)
            for cat, s in category_stats.items()
        }

        # ─── DOMINANT EMOTIONS ───────────────────────────────────
        all_moods = []
        for log in logs:
            for field in [log.morning_extracted, log.evening_extracted]:
                if field and field.get("mood"):
                    all_moods.append(field["mood"])

        mood_counter = Counter(all_moods)
        dominant_emotions = dict(mood_counter.most_common(5))

        # ─── MOOD-PERFORMANCE CORRELATION ────────────────────────
        mood_perf_data = []
        for log in logs:
            morning_score = log.morning_feeling_score
            if morning_score is None:
                continue
            day_goals = [gl for gl in goal_logs if gl.log_date == log.log_date]
            if not day_goals:
                continue
            day_rate = sum(1 for gl in day_goals if gl.status == GoalLogStatus.completed) / len(day_goals)
            mood_perf_data.append((morning_score, day_rate))

        mood_perf_corr = _simple_correlation(mood_perf_data) if len(mood_perf_data) >= 5 else None

        # ─── LIFE AREA SCORES ────────────────────────────────────
        life_area_scores = {}
        area_counts = {}
        for log in logs:
            for field in [log.morning_extracted, log.evening_extracted]:
                if field:
                    for area in field.get("life_areas_mentioned", []):
                        energy = field.get("energy_level", 5)
                        life_area_scores[area] = life_area_scores.get(area, 0) + energy
                        area_counts[area] = area_counts.get(area, 0) + 1

        life_area_avg = {
            area: round(life_area_scores[area] / max(area_counts[area], 1), 1)
            for area in life_area_scores
        }

        # ─── SAVE / UPDATE ───────────────────────────────────────
        person = db.query(PersonModel).filter_by(user_id=user_id).first()
        if not person:
            person = PersonModel(user_id=user_id)
            db.add(person)

        person.top_excuses = top_excuses
        person.consistency_style = consistency_style
        person.peak_performance_days = peak_performance_days
        person.goal_dna = goal_dna
        person.life_area_scores = life_area_avg
        person.dominant_emotions = dominant_emotions
        person.mood_performance_correlation = mood_perf_corr
        person.updated_at = datetime.now()

        db.commit()
        logger.info(f"[REFLECTA] Person model updated for user {user_id}: style={consistency_style}")

    except Exception as e:
        logger.error(f"[REFLECTA] Person model build failed for user {user_id}: {e}")
        self.retry(exc=e)
    finally:
        db.close()


def _simple_correlation(pairs: list) -> float:
    """Simple Pearson correlation between mood scores and goal completion rates."""
    n = len(pairs)
    if n < 2:
        return 0.0

    x_vals = [p[0] for p in pairs]
    y_vals = [p[1] for p in pairs]

    x_mean = sum(x_vals) / n
    y_mean = sum(y_vals) / n

    numerator = sum((x - x_mean) * (y - y_mean) for x, y in pairs)
    x_var = sum((x - x_mean) ** 2 for x in x_vals)
    y_var = sum((y - y_mean) ** 2 for y in y_vals)

    denominator = (x_var * y_var) ** 0.5
    if denominator == 0:
        return 0.0

    return round(numerator / denominator, 3)
