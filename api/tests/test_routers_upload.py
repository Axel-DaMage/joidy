"""Router tests for the file upload endpoints (#13)."""

import io

from fastapi.testclient import TestClient


def test_upload_image_succeeds(client: TestClient):
    response = client.post(
        "/upload/image",
        files={"file": ("test.png", io.BytesIO(b"fake-png-data"), "image/png")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["url"].startswith("/uploads/")
    assert data["filename"].endswith(".png")
    assert data["mime"] == "image/png"
    assert data["size"] == len(b"fake-png-data")


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
