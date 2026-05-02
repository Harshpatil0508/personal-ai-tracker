import logging
from datetime import date
from calendar import monthrange

logger = logging.getLogger(__name__)


#-------- MONTHLY WINDOW UTILITIES --------



def get_user_monthly_window(first_log_date: date, now: date):
    """
    Returns (start_date, end_date, window_label)
    window_label is YYYY-MM of the END month.
    """

    # First partial month
    if now.year == first_log_date.year and now.month == first_log_date.month:
        start_date = first_log_date
        end_date = date(
            now.year,
            now.month,
            monthrange(now.year, now.month)[1]
        )
    else:
        # Regular calendar month
        start_date = date(now.year, now.month, 1)
        end_date = date(
            now.year,
            now.month,
            monthrange(now.year, now.month)[1]
        )

    window_label = end_date.strftime("%Y-%m")
    return start_date, end_date, window_label
