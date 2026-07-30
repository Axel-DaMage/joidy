"""Tests for Prometheus /metrics endpoint and middleware."""


def test_metrics_endpoint_returns_prometheus_format(client):
    """The /metrics endpoint should return Prometheus-compatible output."""
    resp = client.get("/metrics")
    assert resp.status_code == 200
    text = resp.text
    assert "http_requests_total" in text or "python_info" in text


def test_metrics_middleware_records_requests(client):
    """The metrics middleware should track HTTP request counts."""
    resp = client.get("/notes/")
    assert resp.status_code == 200

    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "http_requests_total" in resp.text
