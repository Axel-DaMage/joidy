"""Google People API contacts service (#43).

Business logic for the dedicated ``/integrations/contacts`` router: Person
normalization, OAuth-scope capability checks and the create/update/delete
orchestration on top of the raw helpers in ``services.google_service``.

Scope model: reads work with ``contacts`` or ``contacts.readonly``; writes
require the full ``contacts`` scope. Tokens granted before the scope bump
only carry ``contacts.readonly`` — write calls are rejected up front with
``ContactsReconsentRequired`` (→ HTTP 403) and Google-side
``insufficientPermissions`` responses are mapped the same way, mirroring the
calendar write-back pattern (#1233).
"""

import logging
import re
from typing import Any

import httpx
from models.google_token import GoogleToken
from services import google_service as gs
from services.google_token_service import get_stored_token
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

CONTACTS_WRITE_SCOPE = "https://www.googleapis.com/auth/contacts"
CONTACTS_READONLY_SCOPE = "https://www.googleapis.com/auth/contacts.readonly"
# Legacy alias: https://www.google.com/m8/feeds grants the same contacts
# read+write access (People API migration guide).
_CONTACTS_WRITE_SCOPES = frozenset({CONTACTS_WRITE_SCOPE, "https://www.google.com/m8/feeds"})
_CONTACTS_READ_SCOPES = _CONTACTS_WRITE_SCOPES | {CONTACTS_READONLY_SCOPE}

_PERSON_RESOURCE_RE = re.compile(r"^people/[A-Za-z0-9_-]+$")
_GROUP_RESOURCE_RE = re.compile(r"^contactGroups/[A-Za-z0-9_-]+$")

# personFields masks. LIST stays lean for the contacts page; DETAIL adds the
# edit-form fields plus memberships (group badges). Mutations answer with
# SAFE_DETAIL — memberships is omitted there so a readonly-scoped token can
# never fail the *response* shaping of a write it is already allowed to do.
LIST_PERSON_FIELDS = "names,emailAddresses,phoneNumbers,photos,organizations"
DETAIL_PERSON_FIELDS = (
    "names,emailAddresses,phoneNumbers,photos,organizations,addresses,birthdays,biographies,urls,memberships"
)
DETAIL_PERSON_FIELDS_SAFE = (
    "names,emailAddresses,phoneNumbers,photos,organizations,addresses,birthdays,biographies,urls"
)


class ContactsReconsentRequired(RuntimeError):
    """The stored Google token lacks the scope a contacts operation needs."""


class ContactsValidationError(ValueError):
    """Invalid client input for the contacts API (→ HTTP 400)."""


def validate_person_resource_name(resource_name: str) -> str:
    """Accept only ``people/{id}`` resource names — nothing else may reach the
    People API path (no traversal into other endpoints/hosts)."""
    if not _PERSON_RESOURCE_RE.match(resource_name):
        raise ContactsValidationError("Invalid contact resource name (expected people/{id})")
    return resource_name


def normalize_group_resource_name(value: str) -> str:
    """Accept ``contactGroups/{id}`` or a bare id and return the resource name."""
    candidate = value.strip()
    if not candidate.startswith("contactGroups/"):
        candidate = f"contactGroups/{candidate}"
    if not _GROUP_RESOURCE_RE.match(candidate):
        raise ContactsValidationError("Invalid contact group resource name (expected contactGroups/{id})")
    return candidate


def _granted_scopes(row: GoogleToken | None) -> set[str] | None:
    """Space-separated OAuth scopes granted to the stored token.

    Returns None when unknown (no row or legacy row without a scope string) —
    callers must not treat unknown as denied.
    """
    if row is None or not row.scope:
        return None
    return set(row.scope.split())


def contacts_capabilities(db: Session) -> tuple[bool | None, bool | None]:
    """(can_read, can_write) for contacts; None entries mean 'unknown'."""
    scopes = _granted_scopes(get_stored_token(db))
    if scopes is None:
        return None, None
    return bool(scopes & _CONTACTS_READ_SCOPES), bool(scopes & _CONTACTS_WRITE_SCOPES)


def require_write_scope(db: Session) -> None:
    """Raise ContactsReconsentRequired when the stored grant provably lacks
    the contacts write scope. Unknown scopes are left to Google's 403 mapping.
    """
    _, can_write = contacts_capabilities(db)
    if can_write is False:
        raise ContactsReconsentRequired(
            "El token de Google no tiene permiso de escritura en Contacts. "
            "Reconecta tu cuenta en Ajustes para habilitar crear, editar y eliminar contactos."
        )


def _reconsent_if_needed(exc: httpx.HTTPStatusError) -> None:
    """Raise ContactsReconsentRequired on 403 insufficientPermissions, else re-raise."""
    response = exc.response
    if response.status_code == 403:
        try:
            body = response.json()
        except Exception:
            body = {}
        errors = body.get("error", {})
        if isinstance(errors, dict) and errors.get("errors"):
            reasons = {e.get("reason") for e in errors["errors"]}
            if "insufficientPermissions" in reasons:
                raise ContactsReconsentRequired(
                    "El token de Google no tiene permiso para Contacts. Reconecta tu cuenta en Ajustes."
                ) from exc
    raise exc


# ---------------------------------------------------------------------------
# Normalization — Google Person → flat snake_case dict for the frontend
# ---------------------------------------------------------------------------


def _is_primary(item: dict[str, Any]) -> bool:
    return bool((item.get("metadata") or {}).get("primary"))


def _pick_primary(items: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    """Google guarantees one entry per non-empty field has metadata.primary."""
    if not items:
        return None
    for item in items:
        if _is_primary(item):
            return item
    return items[0]


def _norm_typed(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "value": item.get("value"),
        "type": item.get("type"),
        "primary": _is_primary(item),
    }


def _norm_name(name: dict[str, Any] | None) -> dict[str, Any]:
    name = name or {}
    display = name.get("displayName") or name.get("unstructuredName")
    if not display:
        display = " ".join(p for p in (name.get("givenName"), name.get("middleName"), name.get("familyName")) if p)
    return {
        "display_name": display or None,
        "given_name": name.get("givenName"),
        "family_name": name.get("familyName"),
        "middle_name": name.get("middleName"),
        "honorific_prefix": name.get("honorificPrefix"),
        "honorific_suffix": name.get("honorificSuffix"),
    }


def _norm_email(email: dict[str, Any]) -> dict[str, Any]:
    return {
        "value": email.get("value"),
        "type": email.get("type"),
        "primary": _is_primary(email),
        "display_name": email.get("displayName"),
    }


def _norm_organization(org: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": org.get("name"),
        "title": org.get("title"),
        "department": org.get("department"),
        "type": org.get("type"),
        "current": org.get("current"),
        "job_description": org.get("jobDescription"),
        "primary": _is_primary(org),
    }


def _norm_address(addr: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": addr.get("type"),
        "formatted_value": addr.get("formattedValue"),
        "po_box": addr.get("poBox"),
        "street_address": addr.get("streetAddress"),
        "extended_address": addr.get("extendedAddress"),
        "city": addr.get("city"),
        "region": addr.get("region"),
        "postal_code": addr.get("postalCode"),
        "country": addr.get("country"),
        "country_code": addr.get("countryCode"),
        "primary": _is_primary(addr),
    }


def _norm_birthday(bday: dict[str, Any]) -> dict[str, Any]:
    date = bday.get("date") or {}
    # Google Date uses 0 for "unset" components — expose None instead.
    return {
        "year": date.get("year") or None,
        "month": date.get("month") or None,
        "day": date.get("day") or None,
        "text": bday.get("text"),
    }


def _norm_memberships(person: dict[str, Any]) -> list[str]:
    groups: list[str] = []
    for membership in person.get("memberships") or []:
        group = (membership.get("contactGroupMembership") or {}).get("contactGroupResourceName")
        if group:
            groups.append(group)
    return groups


def normalize_person(person: dict[str, Any]) -> dict[str, Any]:
    """Flatten a Google Person resource into the API's contact shape."""
    name = _norm_name(_pick_primary(person.get("names")))
    photos = person.get("photos") or []
    photo = _pick_primary(photos)
    biographies = person.get("biographies") or []
    bio = _pick_primary(biographies)

    out: dict[str, Any] = {
        "resource_name": person.get("resourceName"),
        "etag": person.get("etag"),
    }
    out.update(name)
    out["emails"] = [_norm_email(e) for e in person.get("emailAddresses") or []]
    out["phones"] = [_norm_typed(p) for p in person.get("phoneNumbers") or []]
    out["organizations"] = [_norm_organization(o) for o in person.get("organizations") or []]
    out["addresses"] = [_norm_address(a) for a in person.get("addresses") or []]
    out["birthdays"] = [_norm_birthday(b) for b in person.get("birthdays") or []]
    out["urls"] = [_norm_typed(u) for u in person.get("urls") or []]
    out["photo_url"] = photo.get("url") if photo else None
    out["note"] = bio.get("value") if bio else None
    out["memberships"] = _norm_memberships(person)
    return out


def normalize_group(group: dict[str, Any]) -> dict[str, Any]:
    """Flatten a ContactGroup resource."""
    return {
        "resource_name": group.get("resourceName"),
        "name": group.get("name"),
        "formatted_name": group.get("formattedName"),
        "group_type": group.get("groupType"),
        "member_count": group.get("memberCount"),
    }


# ---------------------------------------------------------------------------
# Write payload — flat API fields → Google Person resource + update mask
# ---------------------------------------------------------------------------

_NAME_FIELD_MAP = {
    "given_name": "givenName",
    "family_name": "familyName",
    "middle_name": "middleName",
    "honorific_prefix": "honorificPrefix",
    "honorific_suffix": "honorificSuffix",
    "unstructured_name": "unstructuredName",
}

_ADDRESS_FIELD_MAP = {
    "type": "type",
    "formatted_value": "formattedValue",
    "po_box": "poBox",
    "street_address": "streetAddress",
    "extended_address": "extendedAddress",
    "city": "city",
    "region": "region",
    "postal_code": "postalCode",
    "country": "country",
    "country_code": "countryCode",
}

_ORG_FIELD_MAP = {
    "name": "name",
    "title": "title",
    "department": "department",
    "type": "type",
    "current": "current",
    "job_description": "jobDescription",
}


def _clean_entry(raw: dict[str, Any], field_map: dict[str, str], *, with_metadata: bool = True) -> dict[str, Any]:
    """Map snake_case input keys to Google camelCase, dropping unset values."""
    entry: dict[str, Any] = {}
    for src, dst in field_map.items():
        value = raw.get(src)
        if value is not None:
            entry[dst] = value
    if with_metadata and raw.get("primary") is not None:
        # FieldMetadata.primary is output-only; sourcePrimary is the writable
        # flag Google uses to pick the primary entry per source.
        entry["metadata"] = {"sourcePrimary": bool(raw["primary"])}
    return entry


def _build_typed_list(items: Any, field_map: dict[str, str]) -> list[dict[str, Any]]:
    return [_clean_entry(item, field_map) for item in items or [] if isinstance(item, dict)]


def build_person(data: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Build a Google Person payload from the flat write model.

    ``data`` must contain only keys the client explicitly set
    (``model_dump(exclude_unset=True)``). Returns (person, update_fields)
    where update_fields is the comma-joinable list of top-level Person field
    names for ``updatePersonFields`` — each provided section maps to exactly
    one Google field and fully replaces it.
    """
    person: dict[str, Any] = {}
    update_fields: list[str] = []

    if any(key in data for key in _NAME_FIELD_MAP):
        name = _clean_entry(data, _NAME_FIELD_MAP, with_metadata=False)
        person["names"] = [name] if name else []
        update_fields.append("names")

    if "emails" in data:
        person["emailAddresses"] = _build_typed_list(
            data["emails"], {"value": "value", "type": "type", "display_name": "displayName"}
        )
        update_fields.append("emailAddresses")

    if "phones" in data:
        person["phoneNumbers"] = _build_typed_list(data["phones"], {"value": "value", "type": "type"})
        update_fields.append("phoneNumbers")

    if "organizations" in data:
        person["organizations"] = _build_typed_list(data["organizations"], _ORG_FIELD_MAP)
        update_fields.append("organizations")

    if "addresses" in data:
        person["addresses"] = _build_typed_list(data["addresses"], _ADDRESS_FIELD_MAP)
        update_fields.append("addresses")

    if "birthdays" in data:
        birthdays: list[dict[str, Any]] = []
        for raw in data["birthdays"] or []:
            if not isinstance(raw, dict):
                continue
            entry: dict[str, Any] = {}
            date = {k: raw.get(k) for k in ("year", "month", "day") if raw.get(k) is not None}
            if date:
                entry["date"] = date
            if raw.get("text"):
                entry["text"] = raw["text"]
            if entry:
                birthdays.append(entry)
        person["birthdays"] = birthdays
        update_fields.append("birthdays")

    if "note" in data:
        note = data["note"]
        person["biographies"] = [{"value": note, "contentType": "TEXT"}] if note else []
        update_fields.append("biographies")

    if "urls" in data:
        person["urls"] = _build_typed_list(data["urls"], {"value": "value", "type": "type"})
        update_fields.append("urls")

    if "memberships" in data:
        person["memberships"] = [
            {"contactGroupMembership": {"contactGroupResourceName": normalize_group_resource_name(g)}}
            for g in data["memberships"] or []
            if isinstance(g, str)
        ]
        update_fields.append("memberships")

    return person, update_fields


def _contact_sources(person: dict[str, Any], client_etag: str | None) -> list[dict[str, Any]]:
    """Extract writable metadata.sources for updateContact.

    Google requires ``person.metadata.sources`` (with a CONTACT source) on
    every updateContact call; we re-read the person and echo its sources back,
    injecting the client's etag when provided so a stale write fails with
    ``failedPrecondition`` instead of silently overwriting.
    """
    sources = ((person.get("metadata") or {}).get("sources")) or []
    contact_sources = [s for s in sources if isinstance(s, dict) and s.get("type") == "CONTACT"]
    chosen = contact_sources or [s for s in sources if isinstance(s, dict)]
    out: list[dict[str, Any]] = []
    for source in chosen:
        entry = {"type": source.get("type"), "id": source.get("id"), "etag": client_etag or source.get("etag")}
        out.append({k: v for k, v in entry.items() if v is not None})
    return out


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def list_contacts(
    token: str,
    *,
    query: str | None = None,
    group: str | None = None,
    page_size: int = 100,
    page_token: str | None = None,
) -> dict[str, Any]:
    """List/search contacts.

    ``query`` → people:searchContacts (no pagination, capped at 30 results).
    ``group`` → connections.list filtered by the group's memberResourceNames
    (one Google page per request; next_page_token resumes the scan).
    """
    if query:
        try:
            data = await gs.search_contacts(token, query, LIST_PERSON_FIELDS, page_size)
        except httpx.HTTPStatusError as exc:
            _reconsent_if_needed(exc)
        contacts = [
            normalize_person(result.get("person") or {})
            for result in data.get("results", [])
            if isinstance(result, dict)
        ]
        return {"contacts": contacts, "next_page_token": None, "total_items": None}

    member_names: set[str] | None = None
    if group:
        group_resource = normalize_group_resource_name(group)
        try:
            group_data = await gs.get_contact_group(token, group_resource)
        except httpx.HTTPStatusError as exc:
            _reconsent_if_needed(exc)
        member_names = set(group_data.get("memberResourceNames") or [])
        total_members = group_data.get("memberCount")
        if total_members is not None and total_members > len(member_names):
            logger.warning(
                "[contacts] group %s truncated: memberCount=%s but only %s member names returned",
                group_resource,
                total_members,
                len(member_names),
            )

    try:
        data = await gs.list_connections(token, LIST_PERSON_FIELDS, page_size, page_token)
    except httpx.HTTPStatusError as exc:
        _reconsent_if_needed(exc)

    connections = [c for c in data.get("connections", []) if isinstance(c, dict)]
    if member_names is not None:
        connections = [c for c in connections if c.get("resourceName") in member_names]

    return {
        "contacts": [normalize_person(c) for c in connections],
        "next_page_token": data.get("nextPageToken"),
        "total_items": data.get("totalItems"),
    }


async def get_contact(token: str, resource_name: str) -> dict[str, Any]:
    """Fetch one contact. Retries without ``memberships`` if Google rejects
    the field mask for the granted scopes (defensive — memberships is expected
    to be readable under contacts.readonly)."""
    resource_name = validate_person_resource_name(resource_name)
    try:
        person = await gs.get_person(token, resource_name, DETAIL_PERSON_FIELDS)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in (400, 403):
            try:
                person = await gs.get_person(token, resource_name, DETAIL_PERSON_FIELDS_SAFE)
            except httpx.HTTPStatusError as exc2:
                _reconsent_if_needed(exc2)
                raise
        else:
            _reconsent_if_needed(exc)
            raise
    return normalize_person(person)


async def create_contact(token: str, data: dict[str, Any]) -> dict[str, Any]:
    """Create a contact via people:createContact."""
    person, _update_fields = build_person(data)
    try:
        created = await gs.create_contact(token, person, DETAIL_PERSON_FIELDS_SAFE)
    except httpx.HTTPStatusError as exc:
        _reconsent_if_needed(exc)
    return normalize_person(created)


async def update_contact(
    token: str,
    resource_name: str,
    data: dict[str, Any],
    etag: str | None = None,
) -> dict[str, Any]:
    """Update a contact via people:updateContact.

    Google requires ``metadata.sources`` on the update body, so the current
    person is fetched first (personFields=metadata only). ``etag`` — when the
    client echoes back the one from a previous read — is injected into the
    contact source so a concurrent edit fails with failedPrecondition (409).
    """
    resource_name = validate_person_resource_name(resource_name)
    person, update_fields = build_person(data)
    if not update_fields:
        raise ContactsValidationError("No contact fields to update")

    try:
        current = await gs.get_person(token, resource_name, "metadata")
    except httpx.HTTPStatusError as exc:
        _reconsent_if_needed(exc)
        raise

    sources = _contact_sources(current, etag)
    if sources:
        person["metadata"] = {"sources": sources}

    try:
        updated = await gs.update_contact(
            token,
            resource_name,
            person,
            ",".join(update_fields),
            DETAIL_PERSON_FIELDS_SAFE,
        )
    except httpx.HTTPStatusError as exc:
        _reconsent_if_needed(exc)
        raise
    return normalize_person(updated)


async def delete_contact(token: str, resource_name: str) -> None:
    """Delete a contact via people:deleteContact."""
    resource_name = validate_person_resource_name(resource_name)
    try:
        await gs.delete_contact(token, resource_name)
    except httpx.HTTPStatusError as exc:
        _reconsent_if_needed(exc)
        raise


async def list_contact_groups(
    token: str,
    page_size: int = 100,
    page_token: str | None = None,
) -> dict[str, Any]:
    """List the user's contact groups (contactGroups.list)."""
    try:
        data = await gs.list_contact_groups(token, page_size, page_token)
    except httpx.HTTPStatusError as exc:
        _reconsent_if_needed(exc)
    return {
        "groups": [normalize_group(g) for g in data.get("contactGroups", []) if isinstance(g, dict)],
        "next_page_token": data.get("nextPageToken"),
        "total_items": data.get("totalItems"),
    }
