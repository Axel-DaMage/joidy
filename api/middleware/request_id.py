"""
Request ID middleware for distributed tracing.
"""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Adds a unique request ID to each request for tracing."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers['X-Request-ID'] = request_id

        return response


def get_request_id(request: Request) -> str:
    """Get request ID from request state, or generate a new one."""
    return getattr(request.state, 'request_id', str(uuid.uuid4()))
