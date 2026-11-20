"""joidy notes — the AC's canonical example lives here."""

import httpx

from tests.conftest import combined, last_body, output_json

NOTE = {"id": 42, "title": "T", "content": "hello", "tags": [], "source": "api"}


def test_notes_new_from_stdin(invoke, api):
    # AC: cat note.md | joidy notes new --title "T" --content - --json
    api.respond["fn"] = lambda req: httpx.Response(201, json=NOTE)
    result = invoke("notes", "new", "--title", "T", "--content", "-", "--json", stdin="hello\n")
    assert result.exit_code == 0, combined(result)

    request = api.records[-1]
    assert request.method == "POST"
    assert request.url.path == "/notes/"
    body = last_body(api)
    assert body["title"] == "T"
    assert body["content"] == "hello\n"
    assert body["tags"] == []

    data = output_json(result)
    assert data["id"] == 42


def test_notes_new_with_tags(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(201, json=NOTE)
    result = invoke("notes", "new", "--title", "T", "--content", "c", "--tag", "a", "--tag", "b")
    assert result.exit_code == 0
    assert last_body(api)["tags"] == ["a", "b"]


def test_notes_new_requires_title_non_tty(invoke, api):
    result = invoke("notes", "new", "--content", "x")
    assert result.exit_code == 2
    assert "--title" in combined(result)


def test_notes_ls(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(200, json=[NOTE])
    result = invoke("notes", "ls", "--tag", "work", "--limit", "10")
    assert result.exit_code == 0
    request = api.records[-1]
    assert request.url.path == "/notes/"
    assert request.url.params["tag"] == "work"
    assert request.url.params["limit"] == "10"
    assert output_json(result) == [NOTE]


def test_notes_get(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(200, json=NOTE)
    result = invoke("notes", "get", "42")
    assert result.exit_code == 0
    assert api.records[-1].url.path == "/notes/42"
    assert output_json(result)["title"] == "T"


def test_notes_get_404(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(404, json={"detail": "Note not found"})
    result = invoke("notes", "get", "42")
    assert result.exit_code == 4


def test_notes_edit(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(200, json={**NOTE, "title": "T2"})
    result = invoke("notes", "edit", "42", "--title", "T2")
    assert result.exit_code == 0
    assert api.records[-1].method == "PUT"
    assert last_body(api) == {"title": "T2"}


def test_notes_edit_nothing(invoke, api):
    result = invoke("notes", "edit", "42")
    assert result.exit_code == 2


def test_notes_rm_requires_yes_non_tty(invoke, api):
    result = invoke("notes", "rm", "42")
    assert result.exit_code == 2
    assert api.records == []  # nothing was sent


def test_notes_rm_with_yes(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(204)
    result = invoke("notes", "rm", "42", "--yes")
    assert result.exit_code == 0
    assert api.records[-1].method == "DELETE"
    assert api.records[-1].url.path == "/notes/42"
    assert output_json(result)["status"] == "deleted"


def test_notes_jq_filter(invoke, api):
    api.respond["fn"] = lambda req: httpx.Response(200, json=[NOTE, {**NOTE, "id": 7}])
    result = invoke("notes", "ls", "--jq", "[].id")
    assert result.exit_code == 0
    assert output_json(result) == [42, 7]
