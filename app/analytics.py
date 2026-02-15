import pandas as pd

def generate_monthly_summary(daily_logs):
    df = pd.DataFrame(daily_logs)

    if df.empty:
        return None

    summary = {
        "avg_work_hours": round(df["work_hours"].mean(), 2),
        "avg_study_hours": round(df["study_hours"].mean(), 2),
        "avg_sleep_hours": round(df["sleep_hours"].mean(), 2),

        # already percentage in DB
        "goal_completion_rate": round(df["goal_completed"].mean(), 2),

        "avg_mood": round(df["mood_score"].mean(), 2),
        "total_days_logged": len(df),
    }

    # ---- Trend Detection ----
    if len(df) >= 7:
        mid = len(df) // 2
        first = df.iloc[:mid]["work_hours"].mean()
        second = df.iloc[mid:]["work_hours"].mean()

        diff = second - first

        if abs(diff) < 0.25:
            summary["work_trend"] = "stable"
        elif diff > 0:
            summary["work_trend"] = "improving"
        else:
            summary["work_trend"] = "declining"
    else:
        summary["work_trend"] = "insufficient_data"

    return summary
