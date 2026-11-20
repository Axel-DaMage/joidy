"""Tests for HTTP security response headers (#1283, audit F-11).

Verifies that SecurityHeadersMiddleware emits the defense-in-depth headers
on all responses — including error paths — that the interactive API docs
are exempt from the restrictive CSP (they load assets from cdn.jsdelivr.net
and would otherwise break), and that files served from /uploads with
browser-renderable extensions are forced to Content-Disposition: attachment
(audit F-07).
"""

from pathlib import Path

from config import settings
from fastapi.testclient import TestClient

EXPECTED_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
}


def test_security_headers_on_health(client: TestClient):
    """Baseline headers are present on a normal JSON response."""
    response = client.get("/health")
    assert response.status_code == 200
    for header, expected in EXPECTED_HEADERS.items():
        assert response.headers.get(header) == expected, f"missing/incorrect {header}"
    assert response.headers["content-security-policy"] == ("default-src 'none'; frame-ancestors 'none'")


def test_security_headers_on_error_response(client: TestClient):
    """Headers are also emitted on error responses (404 from the router)."""
    response = client.get("/this-endpoint-does-not-exist")
    assert response.status_code == 404
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "content-security-policy" in response.headers


def test_docs_exempt_from_csp(client: TestClient):
    """/docs (Swagger UI) keeps the other headers but skips the deny-all CSP.

    Swagger UI loads JS/CSS from cdn.jsdelivr.net plus an inline bootstrap
    script; `default-src 'none'` would break it. Docs are dev-only — they
    are disabled entirely under APP_ENV=production.
    """
    response = client.get("/docs")
    assert response.status_code == 200
    assert "content-security-policy" not in response.headers
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_uploads_active_content_served_as_attachment(client: TestClient):
    """An .html file under /uploads must be served as an attachment (F-07).

    SafeStaticFiles guards the extension/mime confusion vector: a file
    stored as ``evil.html`` would otherwise be served as text/html and
    render inline in the app origin.
    """
    import main as main_module

    if not main_module._uploads_available:
        return  # uploads mount disabled on this platform — nothing to test

    probe = Path(settings.upload_dir) / "xss_probe_test.html"
    try:
        probe.write_text("<script>alert(1)</script>")
        response = client.get(f"/uploads/{probe.name}")
        assert response.status_code == 200
        assert response.headers["content-disposition"] == "attachment"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "content-security-policy" in response.headers
    finally:
        probe.unlink(missing_ok=True)


def test_uploads_regular_file_still_inline(client: TestClient):
    """Images under /uploads keep normal inline serving + baseline headers."""
    import main as main_module

    if not main_module._uploads_available:
        return

    probe = Path(settings.upload_dir) / "probe_test.png"
    try:
        probe.write_text("hello")
        response = client.get(f"/uploads/{probe.name}")
        assert response.status_code == 200
        assert "content-disposition" not in response.headers
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
    finally:
        probe.unlink(missing_ok=True)
