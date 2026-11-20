"""
Per-user rate limiting middleware using sliding window.
"""

import ipaddress
import logging
import time
from dataclasses import dataclass

from config import settings
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Unauthenticated credential/secret endpoints. These are always keyed by the
# direct peer IP — rotating Bearer/API-key headers or spoofed XFF must not
# escape the bucket (#1276).
_STRICT_PATHS = frozenset({"/auth/login", "/config/setup"})
_STRICT_PREFIXES = ("/webhook/",)


@dataclass
class UserLimit:
    requests: list[float]
    window_size: float = 60.0  # 1 minute window


@dataclass
class LoginAttempt:
    failures: int = 0
    locked_until: float = 0.0


def _is_strict_path(path: str) -> bool:
    return path in _STRICT_PATHS or any(path.startswith(p) for p in _STRICT_PREFIXES)


def _parse_trusted_proxies(value: str) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    networks = []
    for entry in value.split(","):
        entry = entry.strip()
        if not entry:
            continue
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            logger.warning("Ignoring invalid TRUSTED_PROXIES entry: %s", entry)
    return networks


class UserRateLimiter:
    def __init__(
        self,
        requests_per_minute: int = 60,
        auth_requests_per_minute: int = 5000,
        strict_requests_per_minute: int = 30,
        login_max_failures: int = 5,
        login_lockout_base_seconds: float = 60.0,
        login_lockout_max_seconds: float = 3600.0,
        trusted_proxies: str = "",
    ):
        self.requests_per_minute = requests_per_minute
        self.auth_requests_per_minute = auth_requests_per_minute
        self.strict_requests_per_minute = strict_requests_per_minute
        self.login_max_failures = login_max_failures
        self.login_lockout_base_seconds = login_lockout_base_seconds
        self.login_lockout_max_seconds = login_lockout_max_seconds
        self.window_size = 60.0
        self._trusted_networks = _parse_trusted_proxies(trusted_proxies)
        # Plain dict (not defaultdict): entries are created on demand and
        # removed once their window empties out, so inactive IPs/tokens/keys
        # don't accumulate forever (previously a monotonic memory leak).
        self._user_windows: dict[str, UserLimit] = {}
        # Consecutive login failures per peer IP → escalating lockout (#1276).
        self._login_attempts: dict[str, LoginAttempt] = {}
        self._max_login_attempts = 10_000

    def _client_ip(self, request: Request) -> str:
        """Direct peer IP; X-Forwarded-For is honored only when the peer is a
        configured trusted proxy (#1276)."""
        peer = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("X-Forwarded-For")
        if not forwarded or not self._trusted_networks:
            return peer
        try:
            peer_addr = ipaddress.ip_address(peer)
        except ValueError:
            return peer
        if not any(peer_addr in net for net in self._trusted_networks):
            return peer
        return forwarded.split(",")[0].strip() or peer

    def _get_limit_for_request(self, request: Request) -> tuple[str, int]:
        """Extract identifier and limit for rate limiting."""
        # Strict routes first: credential endpoints are keyed by peer IP no
        # matter which auth headers the request carries (#1276).
        path = request.url.path.rstrip("/") or "/"
        if _is_strict_path(path):
            return f"strict:{path}:{self._client_ip(request)}", self.strict_requests_per_minute

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
        return f"ip:{self._client_ip(request)}", self.requests_per_minute

    def _clean_old_requests(self, user_limit: UserLimit, now: float):
        """Remove requests outside the current window."""
        cutoff = now - user_limit.window_size
        user_limit.requests = [ts for ts in user_limit.requests if ts > cutoff]

    def _get_or_create_window(self, identifier: str) -> UserLimit:
        user_limit = self._user_windows.get(identifier)
        if user_limit is None:
            user_limit = UserLimit(requests=[], window_size=self.window_size)
            self._user_windows[identifier] = user_limit
        return user_limit

    def _maybe_evict(self, identifier: str, user_limit: UserLimit) -> None:
        """Drop the window entry if it has no active requests, keeping the
        dict bounded over time."""
        if not user_limit.requests:
            self._user_windows.pop(identifier, None)

    def check_rate_limit(self, request: Request) -> tuple[bool, int]:
        """Returns (allowed, limit)."""
        identifier, limit = self._get_limit_for_request(request)
        now = time.time()

        user_limit = self._get_or_create_window(identifier)
        self._clean_old_requests(user_limit, now)

        if len(user_limit.requests) >= limit:
            # Window is non-empty (at capacity), so keep the entry.
            return False, limit

        user_limit.requests.append(now)
        return True, limit

    def get_remaining(self, request: Request, limit: int) -> int:
        """Get remaining requests for identifier in current window."""
        identifier, _ = self._get_limit_for_request(request)
        now = time.time()
        user_limit = self._user_windows.get(identifier)
        if user_limit is None:
            return limit
        self._clean_old_requests(user_limit, now)
        remaining = max(0, limit - len(user_limit.requests))
        self._maybe_evict(identifier, user_limit)
        return remaining

    @staticmethod
    def _is_login(request: Request) -> bool:
        return request.url.path.rstrip("/") == "/auth/login"

    def login_lock_remaining(self, request: Request) -> float:
        """Seconds of /auth/login lockout left for this peer (0 if unlocked)."""
        if not self._is_login(request):
            return 0.0
        attempt = self._login_attempts.get(self._client_ip(request))
        if attempt is None:
            return 0.0
        return max(0.0, attempt.locked_until - time.time())

    def record_login_result(self, request: Request, status_code: int) -> None:
        """Track consecutive 401s on /auth/login and apply exponential lockout.

        The counter only resets on a successful (<400) response, so
        interleaving malformed requests cannot clear it.
        """
        if not self._is_login(request):
            return
        ip = self._client_ip(request)
        if status_code < 400:
            self._login_attempts.pop(ip, None)
            return
        if status_code != 401:
            return
        attempt = self._login_attempts.get(ip)
        if attempt is None:
            if len(self._login_attempts) >= self._max_login_attempts:
                # Bound memory: drop entries whose lockout already expired.
                now = time.time()
                self._login_attempts = {k: v for k, v in self._login_attempts.items() if v.locked_until > now}
            attempt = self._login_attempts.setdefault(ip, LoginAttempt())
        attempt.failures += 1
        if attempt.failures >= self.login_max_failures:
            backoff = self.login_lockout_base_seconds * 2 ** (attempt.failures - self.login_max_failures)
            attempt.locked_until = time.time() + min(backoff, self.login_lockout_max_seconds)


# Default: 60 req/min per IP, 5000 per authenticated key/token, and 30 per
# peer IP on unauthenticated credential routes (#1276).
_default_limiter = UserRateLimiter(
    requests_per_minute=60,
    auth_requests_per_minute=5000,
    strict_requests_per_minute=30,
    trusted_proxies=settings.trusted_proxies,
)


def get_rate_limiter() -> UserRateLimiter:
    return _default_limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: UserRateLimiter | None = None):
        super().__init__(app)
        self.limiter = limiter or _default_limiter

    async def dispatch(self, request: Request, call_next):
        locked_for = self.limiter.login_lock_remaining(request)
        if locked_for > 0:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": {
                        "error": "Rate limit exceeded",
                        "message": "Too many failed login attempts",
                        "remaining": 0,
                        "retry_after": int(locked_for) + 1,
                    }
                },
            )

        allowed, limit = self.limiter.check_rate_limit(request)
        if not allowed:
            remaining = self.limiter.get_remaining(request, limit)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": {
                        "error": "Rate limit exceeded",
                        "message": f"Maximum {limit} requests per minute",
                        "remaining": remaining,
                        "retry_after": 60,
                    }
                },
            )

        response = await call_next(request)
        self.limiter.record_login_result(request, response.status_code)
        remaining = self.limiter.get_remaining(request, limit)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
