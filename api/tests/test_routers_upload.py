"""Router tests for the file upload endpoints (#13)."""

import io
from pathlib import Path

from config import settings
from fastapi.testclient import TestClient


def _upload_dir() -> Path:
    """The directory the /uploads StaticFiles mount was built with."""
    path = Path(settings.upload_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_upload_image_succeeds(client: TestClient):
    png_data = b"\x89PNG\r\n\x1a\n" + b"fake-png-data"
    response = client.post(
        "/upload/image",
        files={"file": ("test.png", io.BytesIO(png_data), "image/png")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["url"].startswith("/uploads/")
    assert data["filename"].endswith(".png")
    assert data["mime"] == "image/png"
    assert data["size"] == len(png_data)


def test_upload_image_magic_bytes_mismatch_rejected(client: TestClient):
    # Client claims PNG but payload is an executable — must be rejected.
    response = client.post(
        "/upload/image",
        files={"file": ("evil.png", io.BytesIO(b"MZ\x90\x00binary"), "image/png")},
    )
    assert response.status_code == 400


def test_upload_image_invalid_type_rejected(client: TestClient):
    response = client.post(
        "/upload/image",
        files={"file": ("test.exe", io.BytesIO(b"binary"), "application/octet-stream")},
    )
    assert response.status_code == 400


def test_upload_file_succeeds(client: TestClient):
    content = b"hello world this is a text file"
    response = client.post(
        "/upload/file",
        files={"file": ("notes.txt", io.BytesIO(content), "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["url"].startswith("/uploads/")
    assert data["mime"] == "text/plain"
    assert data["size"] == len(content)


def test_upload_file_invalid_type_rejected(client: TestClient):
    response = client.post(
        "/upload/file",
        files={"file": ("malware.exe", io.BytesIO(b"bad"), "application/x-msdownload")},
    )
    assert response.status_code == 400


def test_upload_file_size_limit_enforced(client: TestClient, monkeypatch):
    # Lower the limit to 10 bytes so we can exceed it trivially.
    from config import settings

    monkeypatch.setattr(settings, "upload_max_file_bytes", 10)

    response = client.post(
        "/upload/file",
        files={"file": ("big.txt", io.BytesIO(b"x" * 100), "text/plain")},
    )
    assert response.status_code == 413


def test_upload_image_size_limit_enforced(client: TestClient, monkeypatch):
    from config import settings

    monkeypatch.setattr(settings, "upload_max_image_bytes", 5)

    response = client.post(
        "/upload/image",
        files={"file": ("big.png", io.BytesIO(b"x" * 50), "image/png")},
    )
    assert response.status_code == 413


# --- Stored-XSS hardening (#1279) ------------------------------------------


def test_upload_html_filename_stored_with_safe_extension(client: TestClient):
    # A text/plain payload passes magic validation (UTF-8 text), but the stored
    # extension must come from the validated MIME type — never the filename —
    # so "evil.html" can no longer be served inline as text/html.
    payload = b"<html><script>alert(1)</script></html>"
    response = client.post(
        "/upload/file",
        files={"file": ("evil.html", io.BytesIO(payload), "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"].endswith(".txt")
    assert data["url"].endswith(".txt")

    # Defense in depth: the file on disk carries no .html anywhere.
    stored = _upload_dir() / Path(data["url"]).name
    try:
        assert stored.suffix == ".txt"
        assert stored.read_bytes() == payload
    finally:
        stored.unlink(missing_ok=True)


def test_upload_image_extension_derived_from_mime_not_filename(client: TestClient):
    # Same rule for images: a validated PNG named "photo.html" is stored .png.
    png_data = b"\x89PNG\r\n\x1a\n" + b"fake-png-data"
    response = client.post(
        "/upload/image",
        files={"file": ("photo.html", io.BytesIO(png_data), "image/png")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"].endswith(".png")
    assert data["url"].endswith(".png")

    stored = _upload_dir() / Path(data["url"]).name
    stored.unlink(missing_ok=True)


def test_uploaded_file_served_as_attachment_with_nosniff(client: TestClient):
    # Non-image uploads must download, never render inline in the API origin.
    response = client.post(
        "/upload/file",
        files={"file": ("notes.txt", io.BytesIO(b"plain text body"), "text/plain")},
    )
    assert response.status_code == 200
    url = response.json()["url"]
    stored = _upload_dir() / Path(url).name
    try:
        get = client.get(url)
        assert get.status_code == 200
        assert get.headers["x-content-type-options"] == "nosniff"
        assert get.headers["content-disposition"] == "attachment"
    finally:
        stored.unlink(missing_ok=True)


def test_uploaded_image_served_inline_with_nosniff(client: TestClient):
    # Validated raster images still display inline (notes embed them via
    # markdown), but always with nosniff so the declared type is authoritative.
    png_data = b"\x89PNG\r\n\x1a\n" + b"fake-png-data"
    response = client.post(
        "/upload/image",
        files={"file": ("pic.png", io.BytesIO(png_data), "image/png")},
    )
    assert response.status_code == 200
    url = response.json()["url"]
    stored = _upload_dir() / Path(url).name
    try:
        get = client.get(url)
        assert get.status_code == 200
        assert get.headers["x-content-type-options"] == "nosniff"
        assert "attachment" not in get.headers.get("content-disposition", "")
        assert get.headers["content-type"].startswith("image/png")
    finally:
        stored.unlink(missing_ok=True)


def test_legacy_html_upload_served_as_attachment(client: TestClient):
    # Pre-fix deployments may already hold .html files in the upload dir.
    # They must be attachment-served even though their extension says HTML.
    evil = _upload_dir() / "legacy_evil.html"
    evil.write_text("<html><script>alert(1)</script></html>")
    try:
        get = client.get("/uploads/legacy_evil.html")
        assert get.status_code == 200
        assert get.headers["x-content-type-options"] == "nosniff"
        assert get.headers["content-disposition"] == "attachment"
    finally:
        evil.unlink(missing_ok=True)


def test_uploads_require_auth(client: TestClient, persisted_env: Path):
    # With AUTH_PASSWORD configured, /uploads demands a valid JWT — via the
    # Authorization header or the ?token= query param used by <img>/<a> embeds
    # (same pattern as /ws). Unauthenticated requests get 401 (#1279).
    persisted_env.write_text("AUTH_PASSWORD=testpass\nSECRET_KEY=test-secret-key-for-upload-tests\n")

    target = _upload_dir() / "authcheck.txt"
    target.write_text("secret contents")
    try:
        assert client.get("/uploads/authcheck.txt").status_code == 401
        assert client.get("/uploads/authcheck.txt?token=bogus").status_code == 401
        bad = client.get(
            "/uploads/authcheck.txt",
            headers={"Authorization": "Bearer bogus"},
        )
        assert bad.status_code == 401

        from services.auth_service import create_access_token

        token = create_access_token(1)
        ok_query = client.get(f"/uploads/authcheck.txt?token={token}")
        assert ok_query.status_code == 200
        assert ok_query.headers["x-content-type-options"] == "nosniff"

        ok_header = client.get(
            "/uploads/authcheck.txt",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert ok_header.status_code == 200
        assert ok_header.content == b"secret contents"
    finally:
        target.unlink(missing_ok=True)
