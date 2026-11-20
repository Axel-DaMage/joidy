"""Tests for X-Request-ID validation (#1323).

Only well-formed IDs (^[A-Za-z0-9-]{1,64}$) may be reflected into the
response, logs and upstream calls; anything else is replaced by a
server-generated UUID.
"""

import re

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def test_absent_request_id_is_generated(client):
    resp = client.get("/notes/")
    assert _UUID_RE.match(resp.headers["X-Request-ID"])


def test_valid_request_id_is_reflected(client):
    resp = client.get("/notes/", headers={"X-Request-ID": "req-ABC-123"})
    assert resp.headers["X-Request-ID"] == "req-ABC-123"


def test_max_length_request_id_is_reflected(client):
    rid = "a" * 64
    resp = client.get("/notes/", headers={"X-Request-ID": rid})
    assert resp.headers["X-Request-ID"] == rid


def test_overlong_request_id_is_regenerated(client):
    resp = client.get("/notes/", headers={"X-Request-ID": "a" * 65})
    rid = resp.headers["X-Request-ID"]
    assert rid != "a" * 65
    assert _UUID_RE.match(rid)


def test_request_id_with_invalid_chars_is_regenerated(client):
    # Underscores/spaces are outside the allowlist; the ID must be replaced.
    resp = client.get("/notes/", headers={"X-Request-ID": "bad request_id"})
    assert _UUID_RE.match(resp.headers["X-Request-ID"])
