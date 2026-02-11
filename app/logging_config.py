import logging
import sys
from pythonjsonlogger import jsonlogger


def setup_logging():
    """
    Global JSON structured logging setup.
    Logs go to stdout (best for Docker + Cloud deployments).
    """

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)

    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    handler.setFormatter(formatter)

    # Remove default handlers and add ours
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Reduce noisy logs
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)
