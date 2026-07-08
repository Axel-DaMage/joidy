"""
Per-user rate limiting middleware using sliding window.
"""

import time
from collections import defaultdict
from dataclasses import dataclass

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware


@dataclass
class UserLimit:
    requests: list[float]
    window_size: float = 60.0  # 1 minute window


class UserRateLimiter:
    def __init__(self, requests_per_minute: int = 60, auth_requests_per_minute: int = 120):
        self.requests_per_minute = requests_per_minute
        self.auth_requests_per_minute = auth_requests_per_minute
        self.window_size = 60.0
        self._user_windows: dict[str, UserLimit] = defaultdict(
            lambda: UserLimit(requests=[], window_size=60.0)
        )

    def _get_limit_for_request(self, request: Request) -> tuple[str, int]:
        """Extract identifier and limit for rate limiting."""
        # 1. Check API Key header
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"apikey:{api_key}", self.auth_requests_per_minute

        # 2. Check Authorization Bearer header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1].strip()
            if token:
                # Use prefix/hash to prevent logging sensitive details
                return f"token:{token[:15]}", self.auth_requests_per_minute

        # 3. Fallback to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
        return f"ip:{ip}", self.requests_per_minute

    def _clean_old_requests(self, user_limit: UserLimit, now: float):
        """Remove requests outside the current window."""
        cutoff = now - user_limit.window_size
        user_limit.requests = [ts for ts in user_limit.requests if ts > cutoff]

    def check_rate_limit(self, request: Request) -> tuple[bool, int]:
        """Returns (allowed, limit)."""
        identifier, limit = self._get_limit_for_request(request)
        now = time.time()

        user_limit = self._user_windows[identifier]
        self._clean_old_requests(user_limit, now)

        if len(user_limit.requests) >= limit:
            return False, limit

        user_limit.requests.append(now)
        return True, limit

    def get_remaining(self, request: Request, limit: int) -> int:
        """Get remaining requests for identifier in current window."""
        identifier, _ = self._get_limit_for_request(request)
        now = time.time()
        user_limit = self._user_windows[identifier]
        self._clean_old_requests(user_limit, now)
        return max(0, limit - len(user_limit.requests))


# Default: 60 requests per minute per IP, 120 per authenticated key/token
_default_limiter = UserRateLimiter(requests_per_minute=60, auth_requests_per_minute=120)


def get_rate_limiter() -> UserRateLimiter:
    return _default_limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: UserRateLimiter | None = None):
        super().__init__(app)
        self.limiter = limiter or _default_limiter

    async def dispatch(self, request: Request, call_next):
        allowed, limit = self.limiter.check_rate_limit(request)
        if not allowed:
            remaining = self.limiter.get_remaining(request, limit)
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "message": f"Maximum {limit} requests per minute",
                    "remaining": remaining,
                    "retry_after": 60,
                }
            )

        response = await call_next(request)
        remaining = self.limiter.get_remaining(request, limit)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
