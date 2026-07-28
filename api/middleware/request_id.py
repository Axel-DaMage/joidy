"""
Request ID middleware for distributed tracing.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from middleware.correlation_id import get_correlation_id, set_correlation_id


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Adds a unique request ID to each request for tracing."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Use incoming X-Request-ID or generate one
        request_id = request.headers.get("X-Request-ID") or ""
        request_id = set_correlation_id(request_id)
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def get_request_id(request: Request) -> str:
    """Get request ID from request state, or from context."""
    return getattr(request.state, "request_id", get_correlation_id())
