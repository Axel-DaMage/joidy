"""
Prometheus-compatible metrics middleware and endpoint.
"""

import time
from collections import defaultdict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class MetricsCollector:
    """Collects basic request metrics."""

    def __init__(self):
        self.request_counts = defaultdict(int)
        self.request_times = defaultdict(list)
        self.status_codes = defaultdict(int)

    def record(self, method: str, path: str, status: int, duration_ms: float):
        """Record a request."""
        # Normalize path for grouping
        normalized_path = self._normalize_path(path)
        key = f"{method} {normalized_path}"
        self.request_counts[key] += 1
        self.request_times[key].append(duration_ms)
        self.status_codes[status] += 1

    def _normalize_path(self, path: str) -> str:
        """Normalize path for metrics grouping."""
        # Keep first segment, replace UUIDs/numbers with placeholder
        parts = path.strip("/").split("/")
        if len(parts) > 1:
            return f"{parts[0]}/:id"
        return parts[0] if parts else "root"

    def get_metrics(self) -> dict:
        """Get current metrics."""
        result = {
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
    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000

        _collector.record(
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms
        )

        return response
