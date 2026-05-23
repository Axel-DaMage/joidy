"""
Per-user rate limiting middleware using sliding window.
"""

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware


@dataclass
class UserLimit:
    requests: list[float]
    window_size: float = 60.0  # 1 minute window


class UserRateLimiter:
    def __init__(self, requests_per_minute: int = 60):
        self.requests_per_minute = requests_per_minute
        self.window_size = 60.0
        self._user_windows: dict[str, UserLimit] = defaultdict(
            lambda: UserLimit(requests=[], window_size=60.0)
        )

    def _get_user_id(self, request: Request) -> str:
        """Extract user identifier from request."""
        # Use forwarded header if behind proxy, else client host
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _clean_old_requests(self, user_limit: UserLimit, now: float):
        """Remove requests outside the current window."""
        cutoff = now - user_limit.window_size
        user_limit.requests = [ts for ts in user_limit.requests if ts > cutoff]

    def check_rate_limit(self, request: Request) -> bool:
        """Returns True if request is allowed, False if rate limited."""
        user_id = self._get_user_id(request)
        now = time.time()

        user_limit = self._user_windows[user_id]
        self._clean_old_requests(user_limit, now)

        if len(user_limit.requests) >= self.requests_per_minute:
            return False

        user_limit.requests.append(now)
        return True

    def get_remaining(self, request: Request) -> int:
        """Get remaining requests for user in current window."""
        user_id = self._get_user_id(request)
        now = time.time()
        user_limit = self._user_windows[user_id]
        self._clean_old_requests(user_limit, now)
        return max(0, self.requests_per_minute - len(user_limit.requests))


# Default: 60 requests per minute per IP
_default_limiter = UserRateLimiter(requests_per_minute=60)


def get_rate_limiter() -> UserRateLimiter:
    return _default_limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: Optional[UserRateLimiter] = None):
        super().__init__(app)
        self.limiter = limiter or _default_limiter

    async def dispatch(self, request: Request, call_next):
        if not self.limiter.check_rate_limit(request):
            remaining = self.limiter.get_remaining(request)
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "message": f"Maximum {self.limiter.requests_per_minute} requests per minute",
                    "remaining": remaining,
                    "retry_after": 60,
                }
            )

        response = await call_next(request)
        remaining = self.limiter.get_remaining(request)
        response.headers["X-RateLimit-Limit"] = str(self.limiter.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response