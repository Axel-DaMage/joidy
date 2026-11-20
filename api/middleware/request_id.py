"""
Request ID middleware for distributed tracing.
"""

import re

from middleware.correlation_id import get_correlation_id, set_correlation_id
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Only well-formed IDs are reflected into responses, logs and upstream calls —
# anything else gets replaced with a generated UUID (#1323).
_REQUEST_ID_RE = re.compile(r"[A-Za-z0-9-]{1,64}")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Adds a unique request ID to each request for tracing."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Use incoming X-Request-ID when it is well-formed, else generate one
        incoming = request.headers.get("X-Request-ID") or ""
        if not _REQUEST_ID_RE.fullmatch(incoming):
            incoming = ""
        request_id = set_correlation_id(incoming)
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def get_request_id(request: Request) -> str:
    """Get request ID from request state, or from context."""
    return getattr(request.state, "request_id", get_correlation_id())
