"""Lightweight Prometheus metrics server for the worker.

The worker is not a FastAPI app, so it can't use the same /metrics router
pattern as the API and AI service. Instead, this starts a minimal HTTP server
in a background thread that serves the default Prometheus registry on port
8001, so Prometheus can scrape it alongside the other services (#406).
"""

import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from prometheus_client import Counter, Histogram, generate_latest

import task_status

logger = logging.getLogger(__name__)

# Worker-specific metrics
vault_events_processed = Counter(
    'worker_vault_events_processed_total',
    'Vault events processed',
    ['change_type'],
)
vault_event_errors = Counter(
    'worker_vault_event_errors_total',
    'Vault events that failed processing',
    ['change_type'],
)
vault_event_latency = Histogram(
    'worker_vault_event_latency_seconds',
    'Time to process a vault event',
)
vault_events_pending = Counter(
    'worker_vault_events_pending_recovered_total',
    'Events recovered from the persistent log after a crash',
)

_metrics_server: HTTPServer | None = None


class _MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            body = generate_latest()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/health":
            status = task_status.overall_status()
            tasks = {
                name: {
                    "state": entry["state"],
                    "last_activity": time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(entry["last_activity"])
                    ),
                    "error": entry["error"],
                }
                for name, entry in task_status.snapshot().items()
            }
            body = json.dumps(
                {"status": status, "service": "joidy-worker", "tasks": tasks}
            ).encode()
            code = 200 if status == "ok" else 503
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *_args):
        pass  # Suppress default access logging


def start_metrics_server(port: int = 8001) -> None:
    """Start the metrics HTTP server in a daemon thread."""
    global _metrics_server
    if _metrics_server is not None:
        return
    try:
        _metrics_server = HTTPServer(("0.0.0.0", port), _MetricsHandler)
        thread = threading.Thread(target=_metrics_server.serve_forever, daemon=True, name="metrics-server")
        thread.start()
        logger.info("[worker] Metrics server listening on :%d/metrics", port)
    except Exception as exc:
        logger.warning("[worker] Failed to start metrics server: %s", exc)
