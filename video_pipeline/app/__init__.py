"""Application package initializer.

This file makes the ``app`` directory a Python package. It also
initialises logging when the package is imported.
"""

import logging
import os
from logging.config import dictConfig


def setup_logging():
    """Configure structured JSON logging to stdout.

    Docker captures stdout/stderr, so writing logs to these streams
    allows aggregation by container orchestrators. The format is
    JSON for easy parsing by log analysis tools.
    """
    log_level = os.getenv("LOG_LEVEL", "INFO")
    dictConfig(
        {
            "version": 1,
            "formatters": {
                "json": {
                    "format": "{\"time\": %(asctime)s, \"level\": %(levelname)s, \"message\": %(message)s}"
                }
            },
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {
                "level": log_level,
                "handlers": ["stdout"],
            },
        }
    )

# Initialise logging when the package is imported
setup_logging()