import pandas as pd
from datetime import date

def generate_monthly_summary(daily_logs):
    """
    daily_logs: list of dicts from DB
    """

    df = pd.DataFrame(daily_logs)

    if df.empty:
        return None

    summary = {
        "avg_work_hours": round(df["work_hours"].mean(), 2),
        "avg_study_hours": round(df["study_hours"].mean(), 2),
        "avg_sleep_hours": round(df["sleep_hours"].mean(), 2),
        "goal_completion_rate": round(df["goal_completed"].mean() * 100, 2),
        "avg_mood": round(df["mood_score"].mean(), 2),
        "total_days_logged": len(df)
    }

    # Trend detection (simple & explainable)
    if len(df) >= 7:
        first_half = df.iloc[:len(df)//2]
        second_half = df.iloc[len(df)//2:]

        summary["work_trend"] = (
            "improving"
            if second_half["work_hours"].mean() > first_half["work_hours"].mean()
            else "declining"
        )
    else:
        summary["work_trend"] = "insufficient_data"

    return summary
