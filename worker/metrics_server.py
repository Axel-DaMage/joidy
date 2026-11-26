"""Lightweight Prometheus metrics server for the worker.

The worker is not a FastAPI app, so it can't use the same /metrics router
pattern as the API and AI service. Instead, this starts a minimal HTTP server
in a background thread that serves the default Prometheus registry on port
8001, so Prometheus can scrape it alongside the other services (#406).

The bind address comes from WORKER_BIND_ADDR (#1277): loopback by default
when running outside Docker; docker-compose.yml sets it to 0.0.0.0 since the
port is not published to the host but must be reachable on the internal
compose network (Prometheus on the external `joidy` network, healthchecks).
"""

import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import task_status
from config import settings
from prometheus_client import generate_latest

logger = logging.getLogger(__name__)

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
                    "last_activity": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(entry["last_activity"])),
                    "error": entry["error"],
                }
                for name, entry in task_status.snapshot().items()
            }
            body = json.dumps({"status": status, "service": "joidy-worker", "tasks": tasks}).encode()
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
        _metrics_server = HTTPServer((settings.worker_bind_addr, port), _MetricsHandler)
        thread = threading.Thread(target=_metrics_server.serve_forever, daemon=True, name="metrics-server")
        thread.start()
        logger.info(
            "[worker] Metrics server listening on %s:%d/metrics",
            settings.worker_bind_addr,
            port,
        )
    except Exception as exc:
        logger.warning("[worker] Failed to start metrics server: %s", exc)
