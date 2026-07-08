"""
Structured logging configuration for Joidy Worker.

Mirrors the API logging config: JSON in production, colored human-readable in development.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import settings


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for production environments."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "worker",
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)

        for key in ("file_path", "note_id", "change_type"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class DevFormatter(logging.Formatter):
    """Human-readable formatter with colors for development."""

    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[41m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        reset = self.RESET
        timestamp = datetime.now().strftime("%H:%M:%S")
        return f"{color}{timestamp} {record.levelname:8s}{reset} [{record.name}] {record.getMessage()}"


def setup_logging() -> None:
    """Configure worker logging for console + rotating file."""
    log_dir = Path("/data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    is_production = settings.app_env == "production"

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Avoid duplicate handlers on reload.
    if root.handlers:
        return

    stream = logging.StreamHandler(sys.stdout)
    if is_production:
        stream.setFormatter(JSONFormatter())
    else:
        stream.setFormatter(DevFormatter())
    root.addHandler(stream)

    file_handler = RotatingFileHandler(
        log_dir / "worker.log",
        maxBytes=5_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(JSONFormatter())
    root.addHandler(file_handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
