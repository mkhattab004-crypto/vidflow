"""
Structured logging configuration for VidFlow.
Uses Python's standard logging with a JSON formatter for production
and a human-readable format for development.
"""
import logging
import logging.config
import os
import sys
from datetime import datetime, timezone


class _UTCFormatter(logging.Formatter):
    """Formatter that always uses UTC timestamps."""
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.strftime(datefmt or "%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class JSONFormatter(_UTCFormatter):
    def format(self, record: logging.LogRecord) -> str:
        import json
        payload = {
            "time": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class DevFormatter(_UTCFormatter):
    COLORS = {
        "DEBUG": "\033[94m",
        "INFO": "\033[92m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
        "CRITICAL": "\033[95m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        ts = self.formatTime(record)
        msg = record.getMessage()
        base = f"{color}[{record.levelname:8s}]{self.RESET} {ts} {record.name}: {msg}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def setup_logging(log_level: str = "INFO", json_logs: bool = False) -> None:
    """
    Configure root logger.
    json_logs=True for production (Railway), False for local development.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    formatter = JSONFormatter() if json_logs else DevFormatter()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.setLevel(level)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # Suppress noisy third-party loggers
    for noisy in ["uvicorn.access", "httpx", "httpcore", "google.auth"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        f"Logging configured: level={log_level}, json={json_logs}"
    )
