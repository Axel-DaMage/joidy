"""
Correlation ID context propagation for distributed tracing.

Uses contextvars so that any code running in the same asyncio context
can access the current request's correlation ID without threading it
through every function call.
"""

import logging
import uuid
from contextvars import ContextVar

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    """Return the current correlation ID, or empty string if not set."""
    return correlation_id_var.get()


def set_correlation_id(cid: str | None = None) -> str:
    """Set and return a correlation ID. Generates one if not provided."""
    if not cid:
        cid = str(uuid.uuid4())
    correlation_id_var.set(cid)
    return cid


class CorrelationLogFilter(logging.Filter):
    """Logging filter that attaches the current correlation ID to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_correlation_id()
        return True
