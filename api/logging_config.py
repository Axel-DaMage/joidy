"""
Structured logging configuration for Joidy API.

In production (APP_ENV=production): outputs JSON-formatted log lines for machine parsing.
In development: outputs human-readable colored output.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import settings
from middleware.correlation_id import CorrelationLogFilter


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for production environments."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Include exception info if present
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include extra fields if set via logger.info("msg", extra={...})
        for key in ("request_id", "note_id", "goal_id", "user_id", "duration_ms", "status_code"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class DevFormatter(logging.Formatter):
    """Human-readable formatter with colors for development."""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[41m",  # Red background
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        reset = self.RESET
        timestamp = datetime.now().strftime("%H:%M:%S")
        cid = get_correlation_id()
        prefix = f" [{cid[:8]}]" if cid else ""
        return f"{color}{timestamp} {record.levelname:8s}{reset}{prefix} [{record.name}] {record.getMessage()}"


def setup_logging() -> None:
    """Configure API logging for console + rotating file.

    Uses JSON format in production, colored human-readable in development.
    """
    log_dir = Path("/data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    is_production = settings.app_env == "production"

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Clear existing handlers (like those from uvicorn) so we don't get duplicates or bypassed logging
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    # Console handler
    stream = logging.StreamHandler(sys.stdout)
    if is_production:
        stream.setFormatter(JSONFormatter())
    else:
        stream.setFormatter(DevFormatter())
    stream.addFilter(CorrelationLogFilter())
    root.addHandler(stream)

    # File handler — always JSON for machine parsing
    file_handler = RotatingFileHandler(
        log_dir / "api.log",
        maxBytes=5_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(JSONFormatter())
    file_handler.addFilter(CorrelationLogFilter())
    root.addHandler(file_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
