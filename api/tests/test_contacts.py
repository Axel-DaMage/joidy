"""Tests for the Google Contacts router (#43) — People API proxy.

HTTP to Google is mocked at ``httpx.AsyncClient`` level (same pattern as
test_google.py): ``get`` covers reads, ``request`` covers mutations. Tokens
are stored through ``google_token_service.store_tokens`` so scope checks and
the auto-refresh path run for real. No network, SQLite+PG safe.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from services import google_contacts_service as gccs
from services import google_token_service as gts

GOOGLE_READONLY_SCOPE = (
    "https://www.googleapis.com/auth/contacts.readonly https://www.googleapis.com/auth/calendar.readonly"
)
GOOGLE_WRITE_SCOPE = "https://www.googleapis.com/auth/contacts https://www.googleapis.com/auth/calendar.readonly"

PERSON = {
    "resourceName": "people/c123",
    "etag": "etag-1",
    "names": [
        {
            "givenName": "Ada",
            "familyName": "Lovelace",
            "metadata": {"primary": True},
        }
    ],
    "emailAddresses": [
        {"value": "ada@example.com", "type": "home", "metadata": {"primary": True}},
        {"value": "ada@work.example.com", "type": "work"},
    ],
    "phoneNumbers": [{"value": "+1 555 0100", "type": "mobile", "metadata": {"primary": True}}],
    "organizations": [{"name": "Analytical Engines", "title": "Engineer", "metadata": {"primary": True}}],
    "photos": [{"url": "https://lh3.googleusercontent.com/ada", "metadata": {"primary": True}}],
    "addresses": [{"streetAddress": "12 Main St", "city": "London", "type": "home", "metadata": {"primary": True}}],
    "birthdays": [{"date": {"year": 1815, "month": 12, "day": 10}}],
    "biographies": [{"value": "First programmer", "contentType": "TEXT", "metadata": {"primary": True}}],
    "urls": [{"value": "https://ada.example.com", "type": "homepage"}],
    "memberships": [{"contactGroupMembership": {"contactGroupResourceName": "contactGroups/42"}}],
}

METADATA_PERSON = {
    "resourceName": "people/c123",
    "etag": "etag-2",
    "metadata": {
        "sources": [
            {"type": "PROFILE", "id": "p1", "etag": "prof-etag"},
            {"type": "CONTACT", "id": "c123", "etag": "contact-etag"},
        ]
    },
}


def _fake_response(payload=None, status: int = 200):
    """Success-path mock: json() returns payload; empty payload → empty body."""
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload if payload is not None else {}
    resp.content = b"{}" if payload is not None else b""
    resp.raise_for_status.return_value = None
    return resp


def _http_error(status: int, body: dict | None = None) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://people.googleapis.com/v1/x")
    response = httpx.Response(status, request=request, json=body or {})
    return httpx.HTTPStatusError(f"HTTP {status}", request=request, response=response)


def _connect(db_session, monkeypatch, scope: str = GOOGLE_WRITE_SCOPE) -> None:
    """Store a connected Google token with the given granted scope set."""
    monkeypatch.setattr("config.settings.secret_key", "test-secret")
    gts.store_tokens(
        db_session,
        access_token="ACCESS_TOKEN",
        refresh_token="REFRESH_TOKEN",
        expires_in=3600,
        token_type="Bearer",
        scope=scope,
    )


def _error_response(status: int, body: dict | None = None):
    resp = _fake_response(status=status)
    resp.raise_for_status.side_effect = _http_error(status, body)
    return resp


# ---------------------------------------------------------------------------
# Status & auth
# ---------------------------------------------------------------------------


def test_status_not_connected(client):
    resp = client.get("/integrations/contacts/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is False
    assert data["contacts_read"] is None
    assert data["contacts_write"] is None


def test_status_connected_readonly(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch, GOOGLE_READONLY_SCOPE)
    resp = client.get("/integrations/contacts/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is True
    assert data["contacts_read"] is True
    assert data["contacts_write"] is False


def test_status_connected_write(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch, GOOGLE_WRITE_SCOPE)
    resp = client.get("/integrations/contacts/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["contacts_write"] is True


def test_endpoints_require_auth(client_no_auth):
    assert client_no_auth.get("/integrations/contacts/").status_code == 401
    assert client_no_auth.get("/integrations/contacts/status").status_code == 401
    assert client_no_auth.get("/integrations/contacts/groups").status_code == 401
    assert client_no_auth.post("/integrations/contacts/", json={}).status_code == 401
    assert client_no_auth.get("/integrations/contacts/people/c1").status_code == 401
    assert client_no_auth.delete("/integrations/contacts/people/c1").status_code == 401


def test_list_without_connection_401(client):
    resp = client.get("/integrations/contacts/")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# List / search / group filter
# ---------------------------------------------------------------------------


def test_list_contacts(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    payload = {"connections": [PERSON], "nextPageToken": "tok-2", "totalItems": 42}
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_fake_response(payload))) as mock_get:
        resp = client.get("/integrations/contacts/?page_size=25&page_token=tok-1")

    assert resp.status_code == 200
    data = resp.json()
    assert data["next_page_token"] == "tok-2"
    assert data["total_items"] == 42
    assert len(data["contacts"]) == 1
    contact = data["contacts"][0]
    assert contact["resource_name"] == "people/c123"
    assert contact["display_name"] == "Ada Lovelace"
    assert contact["emails"][0]["value"] == "ada@example.com"
    assert contact["memberships"] == ["contactGroups/42"]

    call = mock_get.call_args_list[0]
    assert call.args[0] == "https://people.googleapis.com/v1/people/me/connections"
    params = call.kwargs["params"]
    assert params["pageSize"] == 25
    assert params["pageToken"] == "tok-1"
    assert "names" in params["personFields"]
    assert "emailAddresses" in params["personFields"]


def test_list_contacts_bare_path(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_fake_response({"connections": []}))):
        resp = client.get("/integrations/contacts")
    assert resp.status_code == 200
    assert resp.json()["contacts"] == []


def test_list_contacts_search(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    payload = {"results": [{"person": PERSON}, {"person": {"resourceName": "people/c9"}}]}
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_fake_response(payload))) as mock_get:
        resp = client.get("/integrations/contacts/?q=ada")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["contacts"]) == 2
    assert data["contacts"][0]["resource_name"] == "people/c123"
    assert data["next_page_token"] is None

    call = mock_get.call_args_list[0]
    assert call.args[0] == "https://people.googleapis.com/v1/people:searchContacts"
    params = call.kwargs["params"]
    assert params["query"] == "ada"
    assert params["readMask"]
    assert params["pageSize"] <= 30


def test_list_contacts_search_query_alias(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_fake_response({"results": []}))) as mock_get:
        resp = client.get("/integrations/contacts/?query=lovelace")
    assert resp.status_code == 200
    assert mock_get.call_args_list[0].kwargs["params"]["query"] == "lovelace"


def test_list_contacts_group_filter(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    group_resp = _fake_response({"memberResourceNames": ["people/c123", "people/c999"], "memberCount": 2})
    conn_resp = _fake_response({"connections": [PERSON, {"resourceName": "people/c777"}], "nextPageToken": "npt"})
    with patch(
        "httpx.AsyncClient.get",
        new=AsyncMock(side_effect=[group_resp, conn_resp]),
    ) as mock_get:
        resp = client.get("/integrations/contacts/?group=contactGroups/42&page_size=50")

    assert resp.status_code == 200
    data = resp.json()
    # Only the member contact survives the filter; the page token still resumes the scan.
    assert [c["resource_name"] for c in data["contacts"]] == ["people/c123"]
    assert data["next_page_token"] == "npt"

    first, second = mock_get.call_args_list
    assert first.args[0] == "https://people.googleapis.com/v1/contactGroups/42"
    assert first.kwargs["params"]["maxMembers"] == 10000
    assert second.args[0] == "https://people.googleapis.com/v1/people/me/connections"


def test_list_contacts_group_bare_id(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    group_resp = _fake_response({"memberResourceNames": [], "memberCount": 0})
    conn_resp = _fake_response({"connections": []})
    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=[group_resp, conn_resp])) as mock_get:
        resp = client.get("/integrations/contacts/?group=42")
    assert resp.status_code == 200
    assert mock_get.call_args_list[0].args[0] == "https://people.googleapis.com/v1/contactGroups/42"


def test_list_contacts_invalid_group(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    resp = client.get("/integrations/contacts/?group=../../admin")
    assert resp.status_code == 400


def test_list_contacts_explicit_token(client):
    """The ``X-Google-Token`` header bypasses the stored-token lookup — the
    legacy ``?token=`` query param was removed (#1461)."""
    payload = {"connections": []}
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_fake_response(payload))) as mock_get:
        resp = client.get("/integrations/contacts/", headers={"X-Google-Token": "xyz"})
    assert resp.status_code == 200
    assert mock_get.call_args_list[0].kwargs["headers"]["Authorization"] == "Bearer xyz"


def test_list_contacts_query_token_ignored(client):
    """``?token=`` must NOT be honored — credentials in URLs leak into logs.
    With no stored connection the request falls through to the stored-token
    path and answers 401 (#1461)."""
    with patch("httpx.AsyncClient.get", new=AsyncMock()) as mock_get:
        resp = client.get("/integrations/contacts/?token=xyz")
    assert resp.status_code == 401
    mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------


def test_get_contact_detail(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_fake_response(PERSON))) as mock_get:
        resp = client.get("/integrations/contacts/people/c123")

    assert resp.status_code == 200
    contact = resp.json()
    assert contact["resource_name"] == "people/c123"
    assert contact["etag"] == "etag-1"
    assert contact["display_name"] == "Ada Lovelace"
    assert contact["family_name"] == "Lovelace"
    assert contact["emails"][1]["value"] == "ada@work.example.com"
    assert contact["organizations"][0]["name"] == "Analytical Engines"
    assert contact["addresses"][0]["city"] == "London"
    assert contact["birthdays"][0] == {"year": 1815, "month": 12, "day": 10, "text": None}
    assert contact["photo_url"] == "https://lh3.googleusercontent.com/ada"
    assert contact["note"] == "First programmer"

    call = mock_get.call_args_list[0]
    assert call.args[0] == "https://people.googleapis.com/v1/people/c123"
    assert "memberships" in call.kwargs["params"]["personFields"]


def test_get_contact_retries_without_memberships(client, db_session, monkeypatch):
    """If Google rejects the memberships field mask, detail degrades gracefully."""
    _connect(db_session, monkeypatch)
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if len(calls) == 1:
            return _error_response(400, {"error": {"message": "Invalid field mask"}})
        return _fake_response(PERSON)

    with patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=fake_get)):
        resp = client.get("/integrations/contacts/people/c123")

    assert resp.status_code == 200
    assert resp.json()["resource_name"] == "people/c123"
    assert "memberships" not in calls[1][1]["params"]["personFields"]


def test_get_contact_invalid_resource_name(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    assert client.get("/integrations/contacts/not-a-person").status_code == 400
    assert client.get("/integrations/contacts/people/c1/extra").status_code == 400
    assert client.get("/integrations/contacts/contactGroups/42").status_code == 400


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def test_create_contact(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.request", new=AsyncMock(return_value=_fake_response(PERSON))) as mock_req:
        resp = client.post(
            "/integrations/contacts/",
            json={
                "given_name": "Ada",
                "family_name": "Lovelace",
                "emails": [{"value": "ada@example.com", "type": "home", "primary": True}],
                "note": "First programmer",
                "memberships": ["42"],
            },
        )

    assert resp.status_code == 200
    assert resp.json()["resource_name"] == "people/c123"

    call = mock_req.call_args_list[0]
    assert call.args[0] == "POST"
    assert call.args[1] == "https://people.googleapis.com/v1/people:createContact"
    body = call.kwargs["json"]
    assert body["names"] == [{"givenName": "Ada", "familyName": "Lovelace"}]
    assert body["emailAddresses"] == [{"value": "ada@example.com", "type": "home", "metadata": {"sourcePrimary": True}}]
    assert body["biographies"] == [{"value": "First programmer", "contentType": "TEXT"}]
    assert body["memberships"] == [{"contactGroupMembership": {"contactGroupResourceName": "contactGroups/42"}}]
    assert "personFields" in call.kwargs["params"]


def test_create_contact_readonly_scope_rejected(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch, GOOGLE_READONLY_SCOPE)
    with patch("httpx.AsyncClient.request", new=AsyncMock()) as mock_req:
        resp = client.post("/integrations/contacts/", json={"given_name": "Ada"})
    assert resp.status_code == 403
    assert "permiso" in resp.json()["detail"] or "scope" in resp.json()["detail"].lower()
    mock_req.assert_not_called()


def test_create_contact_no_connection(client):
    resp = client.post("/integrations/contacts/", json={"given_name": "Ada"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def test_update_contact(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    updated = dict(PERSON, etag="etag-3")
    responses = [_fake_response(METADATA_PERSON), _fake_response(updated)]
    get_mock = AsyncMock(side_effect=responses)
    req_mock = AsyncMock(return_value=_fake_response(updated))
    with (
        patch("httpx.AsyncClient.get", new=get_mock),
        patch("httpx.AsyncClient.request", new=req_mock),
    ):
        resp = client.put(
            "/integrations/contacts/people/c123",
            json={"emails": [{"value": "new@example.com"}], "etag": "client-etag"},
        )

    assert resp.status_code == 200
    assert resp.json()["etag"] == "etag-3"

    # First GET fetches metadata.sources; second call is the PATCH.
    patch_call = req_mock.call_args_list[0]
    assert patch_call.args[0] == "PATCH"
    assert patch_call.args[1] == "https://people.googleapis.com/v1/people/c123:updateContact"
    params = patch_call.kwargs["params"]
    assert params["updatePersonFields"] == "emailAddresses"
    assert "emailAddresses" in params["personFields"]
    body = patch_call.kwargs["json"]
    assert body["emailAddresses"] == [{"value": "new@example.com"}]
    # metadata.sources carries the CONTACT source with the client's etag injected.
    sources = body["metadata"]["sources"]
    assert sources == [{"type": "CONTACT", "id": "c123", "etag": "client-etag"}]


def test_update_contact_without_etag_keeps_google_etag(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    responses = [_fake_response(METADATA_PERSON), _fake_response(PERSON)]
    with (
        patch("httpx.AsyncClient.get", new=AsyncMock(side_effect=responses)),
        patch("httpx.AsyncClient.request", new=AsyncMock(return_value=_fake_response(PERSON))) as req_mock,
    ):
        resp = client.put("/integrations/contacts/people/c123", json={"note": "hello"})

    assert resp.status_code == 200
    body = req_mock.call_args_list[0].kwargs["json"]
    assert body["metadata"]["sources"] == [{"type": "CONTACT", "id": "c123", "etag": "contact-etag"}]
    assert req_mock.call_args_list[0].kwargs["params"]["updatePersonFields"] == "biographies"


def test_update_contact_no_fields_400(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    resp = client.put("/integrations/contacts/people/c123", json={})
    assert resp.status_code == 400


def test_update_contact_readonly_rejected(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch, GOOGLE_READONLY_SCOPE)
    with patch("httpx.AsyncClient.request", new=AsyncMock()) as mock_req:
        resp = client.put("/integrations/contacts/people/c123", json={"note": "x"})
    assert resp.status_code == 403
    mock_req.assert_not_called()


def test_update_contact_invalid_resource_name(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    resp = client.put("/integrations/contacts/bad/name", json={"note": "x"})
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def test_delete_contact(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.request", new=AsyncMock(return_value=_fake_response(None))) as mock_req:
        resp = client.delete("/integrations/contacts/people/c123")

    assert resp.status_code == 200
    assert resp.json() == {"status": "deleted", "resource_name": "people/c123"}
    call = mock_req.call_args_list[0]
    assert call.args[0] == "DELETE"
    assert call.args[1] == "https://people.googleapis.com/v1/people/c123:deleteContact"


def test_delete_contact_readonly_rejected(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch, GOOGLE_READONLY_SCOPE)
    with patch("httpx.AsyncClient.request", new=AsyncMock()) as mock_req:
        resp = client.delete("/integrations/contacts/people/c123")
    assert resp.status_code == 403
    mock_req.assert_not_called()


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------


def test_list_groups(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    payload = {
        "contactGroups": [
            {
                "resourceName": "contactGroups/42",
                "name": "Family",
                "formattedName": "Family",
                "groupType": "USER_CONTACT_GROUP",
                "memberCount": 3,
            },
            {"resourceName": "contactGroups/myContacts", "name": "My Contacts", "groupType": "SYSTEM_CONTACT_GROUP"},
        ],
        "nextPageToken": "gpt",
        "totalItems": 2,
    }
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_fake_response(payload))) as mock_get:
        resp = client.get("/integrations/contacts/groups?page_size=10")

    assert resp.status_code == 200
    data = resp.json()
    assert data["next_page_token"] == "gpt"
    assert data["total_items"] == 2
    assert data["groups"][0] == {
        "resource_name": "contactGroups/42",
        "name": "Family",
        "formatted_name": "Family",
        "group_type": "USER_CONTACT_GROUP",
        "member_count": 3,
    }
    assert data["groups"][1]["resource_name"] == "contactGroups/myContacts"

    call = mock_get.call_args_list[0]
    assert call.args[0] == "https://people.googleapis.com/v1/contactGroups"
    assert call.kwargs["params"]["pageSize"] == 10


def test_groups_route_not_shadowed_by_resource_name(client, db_session, monkeypatch):
    """GET /groups must hit the groups endpoint, not /{resource_name}."""
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_fake_response({"contactGroups": []}))):
        resp = client.get("/integrations/contacts/groups")
    assert resp.status_code == 200
    assert resp.json()["groups"] == []


# ---------------------------------------------------------------------------
# Error mapping
# ---------------------------------------------------------------------------


def test_google_401_maps_to_reconnect(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_error_response(401))):
        resp = client.get("/integrations/contacts/")
    assert resp.status_code == 401
    assert "conecta" in resp.json()["detail"]


def test_insufficient_permissions_maps_to_403(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch, GOOGLE_READONLY_SCOPE)
    body = {"error": {"errors": [{"reason": "insufficientPermissions", "message": "Insufficient Permission"}]}}
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_error_response(403, body))):
        resp = client.get("/integrations/contacts/people/c123")
    assert resp.status_code == 403
    assert "permiso" in resp.json()["detail"]


def test_failed_precondition_maps_to_409(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    body = {"error": {"errors": [{"reason": "failedPrecondition", "message": "etag mismatch"}]}}
    with (
        patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_fake_response(METADATA_PERSON))),
        patch("httpx.AsyncClient.request", new=AsyncMock(return_value=_error_response(400, body))),
    ):
        resp = client.put("/integrations/contacts/people/c123", json={"note": "x"})
    assert resp.status_code == 409


def test_google_500_passthrough(client, db_session, monkeypatch):
    _connect(db_session, monkeypatch)
    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=_error_response(500))):
        resp = client.get("/integrations/contacts/")
    assert resp.status_code == 500
    assert resp.json()["detail"] == "Google API error"


# ---------------------------------------------------------------------------
# Pure unit tests — normalization & payload building
# ---------------------------------------------------------------------------


def test_normalize_person_minimal():
    out = gccs.normalize_person({"resourceName": "people/c1"})
    assert out["resource_name"] == "people/c1"
    assert out["display_name"] is None
    assert out["emails"] == []
    assert out["memberships"] == []


def test_normalize_person_display_name_fallback():
    person = {"names": [{"givenName": "Grace", "familyName": "Hopper"}]}
    out = gccs.normalize_person(person)
    assert out["display_name"] == "Grace Hopper"


def test_normalize_group():
    out = gccs.normalize_group({"resourceName": "contactGroups/9", "name": "Work", "memberCount": 5})
    assert out == {
        "resource_name": "contactGroups/9",
        "name": "Work",
        "formatted_name": None,
        "group_type": None,
        "member_count": 5,
    }


def test_build_person_update_fields():
    person, fields = gccs.build_person(
        {"emails": [{"value": "a@b.c"}], "note": "hi", "memberships": ["contactGroups/1"]}
    )
    assert set(fields) == {"emailAddresses", "biographies", "memberships"}
    assert person["emailAddresses"] == [{"value": "a@b.c"}]
    assert person["biographies"] == [{"value": "hi", "contentType": "TEXT"}]


def test_build_person_empty_update():
    person, fields = gccs.build_person({})
    assert person == {}
    assert fields == []


def test_validate_person_resource_name():
    assert gccs.validate_person_resource_name("people/c123") == "people/c123"
    assert gccs.validate_person_resource_name("people/me") == "people/me"
    with pytest.raises(gccs.ContactsValidationError):
        gccs.validate_person_resource_name("people/c1/extra")
    with pytest.raises(gccs.ContactsValidationError):
        gccs.validate_person_resource_name("contactGroups/1")
    with pytest.raises(gccs.ContactsValidationError):
        gccs.validate_person_resource_name("people/../admin")


def test_normalize_group_resource_name():
    assert gccs.normalize_group_resource_name("42") == "contactGroups/42"
    assert gccs.normalize_group_resource_name("contactGroups/myContacts") == "contactGroups/myContacts"
    with pytest.raises(gccs.ContactsValidationError):
        gccs.normalize_group_resource_name("bad group!")
