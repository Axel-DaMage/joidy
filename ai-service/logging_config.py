"""
Structured logging configuration for Joidy AI Service.

In production (APP_ENV=production): outputs JSON-formatted log lines for machine parsing.
In development: outputs human-readable colored output with correlation IDs.
"""

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import settings

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    return correlation_id_var.get()


def set_correlation_id(cid: str | None = None) -> str:
    if not cid:
        cid = str(uuid.uuid4())
    correlation_id_var.set(cid)
    return cid


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter for production environments."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "ai-service",
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)

        for key in ("request_id", "note_id", "provider", "duration_ms"):
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
        cid = get_correlation_id()
        prefix = f" [{cid[:8]}]" if cid else ""
        return f"{color}{timestamp} {record.levelname:8s}{reset}{prefix} [{record.name}] {record.getMessage()}"


class CorrelationLogFilter(logging.Filter):
    """Attaches the current correlation ID to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_correlation_id()
        return True


def setup_logging() -> None:
    """Configure AI service logging for console + rotating file."""
    log_dir = Path("/data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    is_production = settings.app_env == "production"

    root = logging.getLogger()
    root.setLevel(logging.INFO)

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

    # File handler — always JSON
    file_handler = RotatingFileHandler(
        log_dir / "ai-service.log",
        maxBytes=5_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(JSONFormatter())
    file_handler.addFilter(CorrelationLogFilter())
    root.addHandler(file_handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)