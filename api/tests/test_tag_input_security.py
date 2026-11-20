"""Regression tests for #1322 — tag/bulk endpoint hardening.

Every tag-name input must flow through ``sanitize_tag`` and every bulk list
must be bounded, so oversized or malicious input gets a 422 (never a 500)
and stored tag names can't carry HTML/XSS payloads.
"""

from fastapi.testclient import TestClient

# ── POST /tags/ ────────────────────────────────────────────────────────────────


def test_create_tag_strips_html_chars(client: TestClient):
    """XSS payload chars are stripped; the remaining clean name is stored."""
    res = client.post("/tags/", json={"name": "tag<script>"})
    assert res.status_code == 201
    name = res.json()["name"]
    assert "<" not in name and ">" not in name
    assert name == "tagscript"


def test_create_tag_rejects_oversized_name(client: TestClient):
    res = client.post("/tags/", json={"name": "a" * 200})
    assert res.status_code == 422


def test_create_tag_rejects_empty_after_sanitize(client: TestClient):
    """Names that sanitize to nothing must 422, not create an empty tag."""
    res = client.post("/tags/", json={"name": "<><><>"})
    assert res.status_code == 422
    res = client.post("/tags/", json={"name": "   "})
    assert res.status_code == 422
    res = client.post("/tags/", json={"name": ""})
    assert res.status_code == 422


def test_create_tag_normalizes_valid_name(client: TestClient):
    res = client.post("/tags/", json={"name": "  My Tag!  "})
    assert res.status_code == 201
    assert res.json()["name"] == "my tag"


def test_create_tag_accepts_max_length_name(client: TestClient):
    res = client.post("/tags/", json={"name": "b" * 100})
    assert res.status_code == 201
    assert res.json()["name"] == "b" * 100


# ── Bulk endpoints — list bounds (#1322 DoS) ───────────────────────────────────


def test_bulk_tag_rejects_huge_ids_list(client: TestClient):
    res = client.post("/notes/bulk-tag", json={"ids": list(range(10**6)), "tags": ["x"]})
    assert res.status_code == 422


def test_bulk_tag_rejects_too_many_tags(client: TestClient):
    res = client.post(
        "/notes/bulk-tag",
        json={"ids": [1], "tags": [f"tag-{i}" for i in range(51)]},
    )
    assert res.status_code == 422


def test_bulk_untag_rejects_huge_ids_list(client: TestClient):
    res = client.post("/notes/bulk-untag", json={"ids": list(range(501)), "tags": ["x"]})
    assert res.status_code == 422


def test_bulk_delete_rejects_huge_ids_list(client: TestClient):
    res = client.post("/notes/bulk-delete", json={"ids": list(range(501))})
    assert res.status_code == 422


def test_bulk_endpoints_accept_bounds_at_limit(client: TestClient):
    """Exactly-at-limit payloads pass validation (ids=500, tags=50)."""
    res = client.post("/notes/bulk-delete", json={"ids": list(range(500))})
    assert res.status_code == 200
    res = client.post(
        "/notes/bulk-tag",
        json={"ids": [999999], "tags": [f"tag-{i}" for i in range(50)]},
    )
    assert res.status_code == 200


# ── bulk_tag — sanitized tag names ────────────────────────────────────────────


def test_bulk_tag_sanitizes_tag_names(client: TestClient):
    note = client.post("/notes/", json={"title": "bulk target", "tags": []}).json()
    res = client.post(
        "/notes/bulk-tag",
        json={"ids": [note["id"]], "tags": ["My Tag!", "<b>bold</b>"]},
    )
    assert res.status_code == 200
    tags = client.get(f"/notes/{note['id']}").json()["tags"]
    assert "my tag" in tags
    assert "bboldb" in tags
    # No raw/unsanitized tag name may have been created
    all_names = {t["name"] for t in client.get("/tags/").json()}
    assert "my tag!" not in all_names
    assert "<b>bold</b>" not in all_names


def test_bulk_tag_drops_names_that_sanitize_to_empty(client: TestClient):
    note = client.post("/notes/", json={"title": "bulk target 2", "tags": []}).json()
    res = client.post(
        "/notes/bulk-tag",
        json={"ids": [note["id"]], "tags": ["<><>", "real-tag"]},
    )
    assert res.status_code == 200
    tags = client.get(f"/notes/{note['id']}").json()["tags"]
    assert tags == ["real-tag"]


# ── accept_ai_tag ──────────────────────────────────────────────────────────────


def test_accept_ai_tag_sanitizes_name(client: TestClient):
    note = client.post("/notes/", json={"title": "ai target", "tags": []}).json()
    res = client.post(
        f"/notes/{note['id']}/accept-tag",
        params={"tag_name": "AI Tag!"},
    )
    assert res.status_code == 200
    assert res.json()["tag"] == "ai tag"
    assert "ai tag" in client.get(f"/notes/{note['id']}").json()["tags"]


def test_accept_ai_tag_rejects_oversized_name(client: TestClient):
    res = client.post("/notes/1/accept-tag", params={"tag_name": "a" * 200})
    assert res.status_code == 422


def test_accept_ai_tag_rejects_empty_after_sanitize(client: TestClient):
    res = client.post("/notes/1/accept-tag", params={"tag_name": "<><>"})
    assert res.status_code == 422


# ── Note tag lists — sanitize_tag parity (#1322) ───────────────────────────────


def test_note_create_tags_sanitized(client: TestClient):
    res = client.post(
        "/notes/",
        json={"title": "note tags", "tags": ["Tag One!", "tag<script>"]},
    )
    assert res.status_code == 201
    tags = res.json()["tags"]
    assert "tag one" in tags
    assert "tagscript" in tags


def test_note_create_rejects_too_many_tags(client: TestClient):
    res = client.post(
        "/notes/",
        json={"title": "too many", "tags": [f"tag-{i}" for i in range(51)]},
    )
    assert res.status_code == 422
