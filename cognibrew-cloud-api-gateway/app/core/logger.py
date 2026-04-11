import logging
import os
import sys

from pythonjsonlogger.json import JsonFormatter


def setup_logging() -> None:
    """Configure the root logger with JSON formatting. Call once at startup."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    if log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        log_level = "DEBUG"

    root = logging.getLogger()
    if root.handlers:
        return  # already configured

    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={
            "asctime": "timestamp",
            "levelname": "level",
            "name": "logger",
        },
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level))
