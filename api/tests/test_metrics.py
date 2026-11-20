"""Tests for Prometheus /metrics endpoint and middleware (#1323)."""

from types import SimpleNamespace

from middleware.metrics import MetricsCollector, _route_roots


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


def test_404_spray_collapses_to_single_other_series(client):
    """A spray of unauthenticated 404s must produce one `path="other"` series,
    not one series per invented path (#1323)."""
    for i in range(5):
        resp = client.get(f"/definitely-not-a-route-{i}")
        assert resp.status_code == 404

    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert 'path="other"' in resp.text
    assert "definitely-not-a-route" not in resp.text


def test_known_route_keeps_its_label(client):
    resp = client.get("/notes/")
    assert resp.status_code == 200
    resp = client.get("/metrics")
    assert 'path="notes"' in resp.text


class TestNormalizePath:
    def test_unknown_first_segment_maps_to_other(self):
        c = MetricsCollector()
        roots = frozenset({"notes", "metrics", "root"})
        assert c._normalize_path("/random/path", roots) == "other"
        assert c._normalize_path("/random", roots) == "other"

    def test_known_first_segment_kept(self):
        c = MetricsCollector()
        roots = frozenset({"notes", "root"})
        assert c._normalize_path("/notes", roots) == "notes"
        assert c._normalize_path("/notes/abc-123", roots) == "notes/:id"

    def test_root_path(self):
        c = MetricsCollector()
        assert c._normalize_path("/", frozenset({"root"})) == "root"

    def test_no_known_roots_keeps_legacy_behavior(self):
        c = MetricsCollector()
        assert c._normalize_path("/anything/here") == "anything/:id"


class TestRouteRoots:
    def test_collects_first_segments(self):
        app = SimpleNamespace(
            routes=[
                SimpleNamespace(path="/notes/{note_id}"),
                SimpleNamespace(path="/metrics"),
                SimpleNamespace(path="/"),
            ]
        )
        assert _route_roots(app) == frozenset({"notes", "metrics", "root"})

    def test_walks_nested_included_routers(self):
        # include_router() wraps routers in objects exposing .original_router
        # (whose .routes hold the real paths) — they must count as known.
        included = SimpleNamespace(original_router=SimpleNamespace(routes=[SimpleNamespace(path="/goals/{id}")]))
        app = SimpleNamespace(routes=[included, SimpleNamespace(path="/health")])
        assert _route_roots(app) == frozenset({"goals", "health", "root"})


class TestBoundedState:
    def test_request_times_ring_buffer_is_bounded(self):
        c = MetricsCollector(max_samples_per_key=10)
        for _ in range(50):
            c.record("GET", "/notes", 200, 1.0)
        assert len(c.request_times["GET notes"]) == 10
        assert c.request_counts["GET notes"] == 50

    def test_key_space_is_capped(self):
        c = MetricsCollector(max_keys=3)
        for i in range(10):
            c.record("GET", f"/p{i}", 200, 1.0)
        # 3 real keys + everything else folded into the single "other" bucket.
        assert len(c.request_counts) == 4
        assert c.request_counts["GET other"] == 7

    def test_unknown_methods_fold_into_other(self):
        c = MetricsCollector()
        c.record("PROPFIND", "/notes", 405, 1.0)
        assert c.request_counts["OTHER notes"] == 1
