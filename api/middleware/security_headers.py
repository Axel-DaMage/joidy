"""
HTTP security response headers (issue #1283, audit F-11).

Adds defense-in-depth headers to every API response:

- ``X-Content-Type-Options: nosniff`` — blocks MIME sniffing, so an upload
  stored under a misleading extension can't be reinterpreted as a different
  content type by subresource loads.
- ``X-Frame-Options: DENY`` — legacy clickjacking protection (modern
  equivalent: CSP ``frame-ancestors``).
- ``Referrer-Policy: no-referrer`` — the API must never leak URLs/tokens
  through the ``Referer`` header to third parties.
- ``Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`` —
  API responses are JSON, so a deny-by-default policy is safe; it also
  neutralizes any active content served inline from ``/uploads`` (a
  text/html upload would render with no scripts and no resources, audit
  F-07).
"""

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

_BASE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}

_API_CSP = "default-src 'none'; frame-ancestors 'none'"

# Interactive API docs (/docs, /redoc) load JS/CSS from cdn.jsdelivr.net and
# rely on an inline bootstrap script — a restrictive CSP would break them.
# Docs are only exposed outside production (docs_url/openapi_url are None
# under APP_ENV=production), so exempting them from CSP loses nothing.
_DOCS_PATH_PREFIXES = ("/docs", "/redoc", "/openapi.json")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Set baseline security headers on all responses, including errors.

    Registered last in ``main.py`` so it sits outermost in the middleware
    stack: rate-limit 429s, CORS preflights, and exception-path responses
    all pass through it.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            response: Response = await call_next(request)
        except Exception:
            # Outer middlewares can still raise (e.g. a middleware bug); make
            # sure even those paths emit the headers instead of a bare 500
            # produced outside our scope.
            logger.exception(
                "Unhandled exception above middleware stack: %s %s",
                request.method,
                request.url.path,
            )
            response = JSONResponse(status_code=500, content={"detail": "Internal server error"})

        for header, value in _BASE_HEADERS.items():
            response.headers.setdefault(header, value)

        if not request.url.path.startswith(_DOCS_PATH_PREFIXES):
            response.headers.setdefault("Content-Security-Policy", _API_CSP)

        return response
