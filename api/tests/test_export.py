"""Tests for /export endpoints."""

from models.note import Note


def test_export_notes_markdown(client, db_session):
    note = Note(title="Hello", content="World", source="joidy")
    db_session.add(note)
    db_session.commit()

    resp = client.get("/export/notes/markdown")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/markdown; charset=utf-8"
    body = resp.text
    assert "# Hello" in body
    assert "World" in body


def test_export_notes_html(client, db_session):
    note = Note(title="Hello", content="<b>World</b>", source="joidy")
    db_session.add(note)
    db_session.commit()

    resp = client.get("/export/notes/html")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"
    body = resp.text
    assert "<h1>Hello</h1>" in body
    assert "&lt;b&gt;World&lt;/b&gt;" in body


def test_export_notes_zip(client, db_session):
    note = Note(title="Hello", content="World", source="joidy")
    db_session.add(note)
    db_session.commit()

    resp = client.get("/export/notes/zip")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    assert resp.headers["content-disposition"].startswith("attachment; filename=")
    # The body must be a valid ZIP archive containing the note file.
    import io
    import zipfile

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    names = zf.namelist()
    assert len(names) >= 1
    assert any(name.endswith(".md") for name in names)
    body = zf.read(names[0]).decode("utf-8")
    assert "# Hello" in body
    assert "World" in body


def test_export_notes_html_empty(client):
    resp = client.get("/export/notes/html")
    assert resp.status_code == 404


def test_export_notes_zip_empty(client):
    resp = client.get("/export/notes/zip")
    assert resp.status_code == 404


def test_export_notes_markdown_empty(client):
    resp = client.get("/export/notes/markdown")
    assert resp.status_code == 404


def test_export_notes_markdown_requires_auth(client_no_auth):
    resp = client_no_auth.get("/export/notes/markdown")
    assert resp.status_code == 401


def test_export_notes_html_requires_auth(client_no_auth):
    resp = client_no_auth.get("/export/notes/html")
    assert resp.status_code == 401


def test_export_notes_zip_requires_auth(client_no_auth):
    resp = client_no_auth.get("/export/notes/zip")
    assert resp.status_code == 401
