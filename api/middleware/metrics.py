"""
Prometheus-compatible metrics middleware and endpoint.
"""

import time
from collections import defaultdict, deque

from fastapi import Request
from prometheus_client import Counter, Histogram
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

http_request_duration = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)


# Methods we keep as distinct label values; anything else folds into OTHER so
# a request spray cannot mint unbounded metric series (#1323).
_KNOWN_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})


def _route_roots(app) -> frozenset[str]:
    """First path segments of every registered route.

    Used as the label whitelist: paths that don't map to a real route (404
    sprays, scans) collapse into the single ``other`` series instead of one
    series per invented path (#1323). Routers included via ``include_router``
    appear as wrapper objects that expose their APIRouter through
    ``original_router`` rather than ``.routes`` — walk both so their paths
    count as known too.
    """
    roots = {"root"}
    stack = list(getattr(app, "routes", ()))
    while stack:
        route = stack.pop()
        nested = getattr(route, "routes", None)
        if nested is None:
            nested = getattr(getattr(route, "original_router", None), "routes", None)
        if nested:
            stack.extend(nested)
        route_path = (getattr(route, "path", "") or "").strip("/")
        if route_path:
            roots.add(route_path.split("/")[0])
    return frozenset(roots)


class MetricsCollector:
    """Collects basic request metrics.

    All state is bounded (#1323): per-key timing samples live in a fixed-size
    ring buffer, and the number of distinct ``METHOD path`` keys is capped —
    overflow folds into ``METHOD other``.
    """

    def __init__(self, max_samples_per_key: int = 1000, max_keys: int = 512):
        self.max_samples_per_key = max_samples_per_key
        self.max_keys = max_keys
        self.request_counts: defaultdict[str, int] = defaultdict(int)
        self.request_times: defaultdict[str, deque] = defaultdict(lambda: deque(maxlen=max_samples_per_key))
        self.status_codes: defaultdict[int, int] = defaultdict(int)

    def record(
        self,
        method: str,
        path: str,
        status: int,
        duration_ms: float,
        known_roots: frozenset[str] | None = None,
    ):
        """Record a request."""
        # Normalize path for grouping
        normalized_path = self._normalize_path(path, known_roots)
        method = self._normalize_method(method)
        key = f"{method} {normalized_path}"
        if key not in self.request_counts and len(self.request_counts) >= self.max_keys:
            key = f"{method} other"
        self.request_counts[key] += 1
        self.request_times[key].append(duration_ms)
        self.status_codes[status] += 1

    @staticmethod
    def _normalize_method(method: str) -> str:
        method = method.upper()
        return method if method in _KNOWN_METHODS else "OTHER"

    def _normalize_path(self, path: str, known_roots: frozenset[str] | None = None) -> str:
        """Normalize path for metrics grouping."""
        # Keep first segment, replace UUIDs/numbers with placeholder. When the
        # app's route roots are known, any first segment outside them folds
        # into the single ``other`` label (#1323).
        parts = path.strip("/").split("/")
        first = parts[0] if parts and parts[0] else "root"
        if known_roots is not None and first not in known_roots:
            return "other"
        if len(parts) > 1:
            return f"{first}/:id"
        return first

    def get_metrics(self) -> dict:
        """Get current metrics."""
        result: dict[str, dict] = {
            "requests": {},
            "status_codes": {},
            "summary": {},
        }

        for key, count in self.request_counts.items():
            times = self.request_times[key]
            avg_time = sum(times) / len(times) if times else 0
            p50 = sorted(times)[len(times) // 2] if times else 0
            p95 = sorted(times)[int(len(times) * 0.95)] if times else 0

            result["requests"][key] = {
                "count": count,
                "avg_ms": round(avg_time, 2),
                "p50_ms": round(p50, 2),
                "p95_ms": round(p95, 2),
            }

        for code, count in self.status_codes.items():
            result["status_codes"][str(code)] = count

        total_requests = sum(self.request_counts.values())
        total_time = sum(sum(times) for times in self.request_times.values())
        result["summary"]["total_requests"] = total_requests
        result["summary"]["total_time_ms"] = round(total_time, 2)
        result["summary"]["avg_time_ms"] = round(total_time / total_requests, 2) if total_requests else 0

        return result

    def reset(self):
        """Reset all metrics."""
        self.request_counts.clear()
        self.request_times.clear()
        self.status_codes.clear()


_collector = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    return _collector


class MetricsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        # Lazily resolved on the first request, when request.app is available.
        self._known_roots: frozenset[str] | None = None

    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.perf_counter()
        response: Response = await call_next(request)
        duration = time.perf_counter() - start_time

        if self._known_roots is None:
            self._known_roots = _route_roots(request.app)

        method = _collector._normalize_method(request.method)
        normalized = _collector._normalize_path(request.url.path, self._known_roots)

        _collector.record(
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration * 1000,
            known_roots=self._known_roots,
        )

        http_requests_total.labels(
            method=method,
            path=normalized,
            status=str(response.status_code),
        ).inc()

        http_request_duration.labels(
            method=method,
            path=normalized,
        ).observe(duration)

        return response
