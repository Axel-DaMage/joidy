"""Google Contacts integration router (#43).

Dedicated surface over the Google People API, backed by the shared Google
OAuth connection managed by ``routers/integrations/google.py`` — there is no
separate OAuth flow and no local storage; every call proxies to
people.googleapis.com with the stored (auto-refreshed) access token.

Reads work with ``contacts`` or ``contacts.readonly`` scopes. Writes
(POST/PUT/DELETE) require the full ``contacts`` scope: tokens granted before
the scope bump answer 403 ``ContactsReconsentRequired`` so the client can
prompt a reconnect — same pattern as calendar write-back (#1233).

Token transport (#1461): read endpoints honor an explicit access-token
override via the ``X-Google-Token`` header only — never a ``?token=`` query
param, where credentials would leak into logs (same hardening as
``X-Spotify-Token``/``X-Strava-Token``, #1372).
"""

import httpx
from database import get_db
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from services import google_contacts_service as gccs
from services import google_token_service as gts
from services.auth_service import get_current_user
from sqlalchemy.orm import Session

router = APIRouter(prefix="/integrations/contacts", tags=["integrations"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ContactEmailIn(BaseModel):
    value: str = Field(min_length=1, max_length=320)
    type: str | None = Field(default=None, max_length=64)
    display_name: str | None = Field(default=None, max_length=200)
    primary: bool | None = None


class ContactPhoneIn(BaseModel):
    value: str = Field(min_length=1, max_length=64)
    type: str | None = Field(default=None, max_length=64)
    primary: bool | None = None


class ContactAddressIn(BaseModel):
    type: str | None = Field(default=None, max_length=64)
    formatted_value: str | None = Field(default=None, max_length=512)
    po_box: str | None = Field(default=None, max_length=256)
    street_address: str | None = Field(default=None, max_length=512)
    extended_address: str | None = Field(default=None, max_length=512)
    city: str | None = Field(default=None, max_length=256)
    region: str | None = Field(default=None, max_length=256)
    postal_code: str | None = Field(default=None, max_length=64)
    country: str | None = Field(default=None, max_length=256)
    country_code: str | None = Field(default=None, max_length=8)
    primary: bool | None = None


class ContactOrganizationIn(BaseModel):
    name: str | None = Field(default=None, max_length=512)
    title: str | None = Field(default=None, max_length=512)
    department: str | None = Field(default=None, max_length=512)
    type: str | None = Field(default=None, max_length=64)
    current: bool | None = None
    job_description: str | None = Field(default=None, max_length=2048)
    primary: bool | None = None


class ContactBirthdayIn(BaseModel):
    year: int | None = Field(default=None, ge=0, le=9999)
    month: int | None = Field(default=None, ge=0, le=12)
    day: int | None = Field(default=None, ge=0, le=31)
    text: str | None = Field(default=None, max_length=256)


class ContactUrlIn(BaseModel):
    value: str = Field(min_length=1, max_length=2048)
    type: str | None = Field(default=None, max_length=64)
    primary: bool | None = None


class ContactWriteIn(BaseModel):
    """Flat write model for create/update. Only explicitly-set fields are
    sent to Google (PUT semantics: provided sections fully replace the
    stored ones — send empty lists to clear a section).

    ``memberships`` takes ``contactGroups/{id}`` resource names (bare ids
    are normalized); ``etag`` is update-only optimistic concurrency — echo
    the value returned by a previous read.
    """

    given_name: str | None = Field(default=None, max_length=256)
    family_name: str | None = Field(default=None, max_length=256)
    middle_name: str | None = Field(default=None, max_length=256)
    honorific_prefix: str | None = Field(default=None, max_length=128)
    honorific_suffix: str | None = Field(default=None, max_length=128)
    unstructured_name: str | None = Field(default=None, max_length=512)
    emails: list[ContactEmailIn] = Field(default_factory=list, max_length=20)
    phones: list[ContactPhoneIn] = Field(default_factory=list, max_length=20)
    organizations: list[ContactOrganizationIn] = Field(default_factory=list, max_length=10)
    addresses: list[ContactAddressIn] = Field(default_factory=list, max_length=10)
    birthdays: list[ContactBirthdayIn] = Field(default_factory=list, max_length=5)
    note: str | None = Field(default=None, max_length=4096)
    urls: list[ContactUrlIn] = Field(default_factory=list, max_length=20)
    memberships: list[str] = Field(default_factory=list, max_length=50)
    etag: str | None = Field(default=None, max_length=256)


class ContactEmailOut(BaseModel):
    value: str | None = None
    type: str | None = None
    primary: bool = False
    display_name: str | None = None


class ContactPhoneOut(BaseModel):
    value: str | None = None
    type: str | None = None
    primary: bool = False


class ContactOrganizationOut(BaseModel):
    name: str | None = None
    title: str | None = None
    department: str | None = None
    type: str | None = None
    current: bool | None = None
    job_description: str | None = None
    primary: bool = False


class ContactAddressOut(BaseModel):
    type: str | None = None
    formatted_value: str | None = None
    po_box: str | None = None
    street_address: str | None = None
    extended_address: str | None = None
    city: str | None = None
    region: str | None = None
    postal_code: str | None = None
    country: str | None = None
    country_code: str | None = None
    primary: bool = False


class ContactBirthdayOut(BaseModel):
    year: int | None = None
    month: int | None = None
    day: int | None = None
    text: str | None = None


class ContactUrlOut(BaseModel):
    value: str | None = None
    type: str | None = None
    primary: bool = False


class ContactOut(BaseModel):
    resource_name: str | None = None
    etag: str | None = None
    display_name: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    middle_name: str | None = None
    honorific_prefix: str | None = None
    honorific_suffix: str | None = None
    emails: list[ContactEmailOut] = Field(default_factory=list)
    phones: list[ContactPhoneOut] = Field(default_factory=list)
    organizations: list[ContactOrganizationOut] = Field(default_factory=list)
    addresses: list[ContactAddressOut] = Field(default_factory=list)
    birthdays: list[ContactBirthdayOut] = Field(default_factory=list)
    urls: list[ContactUrlOut] = Field(default_factory=list)
    photo_url: str | None = None
    note: str | None = None
    memberships: list[str] = Field(default_factory=list)


class ContactListOut(BaseModel):
    contacts: list[ContactOut] = Field(default_factory=list)
    next_page_token: str | None = None
    total_items: int | None = None


class ContactGroupOut(BaseModel):
    resource_name: str | None = None
    name: str | None = None
    formatted_name: str | None = None
    group_type: str | None = None
    member_count: int | None = None


class ContactGroupListOut(BaseModel):
    groups: list[ContactGroupOut] = Field(default_factory=list)
    next_page_token: str | None = None
    total_items: int | None = None


class ContactsStatusOut(BaseModel):
    connected: bool
    # None = unknown (legacy token row without a stored scope string).
    contacts_read: bool | None = None
    contacts_write: bool | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _read_token(token: str | None, db: Session) -> str:
    """Resolve the access token for read calls: an explicit ``X-Google-Token``
    header wins, else the stored/auto-refreshed Google token (same semantics
    as google.py). The override arrives by header only — credentials never
    travel in the query string (#1461)."""
    if token:
        return token
    stored = await gts.get_valid_access_token(db)
    if not stored:
        raise HTTPException(status_code=401, detail="Google no está conectado")
    return stored


async def _write_token(db: Session) -> str:
    """Resolve the token for write calls — stored token only, plus a
    proactive scope check so readonly grants fail before hitting Google."""
    stored = await gts.get_valid_access_token(db)
    if not stored:
        raise HTTPException(status_code=401, detail="Google no está conectado")
    try:
        gccs.require_write_scope(db)
    except gccs.ContactsReconsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return stored


def _google_error_reasons(exc: httpx.HTTPStatusError) -> set:
    """Extract google.rpc error reasons (insufficientPermissions, ...) if present."""
    try:
        body = exc.response.json()
    except Exception:
        return set()
    errors = body.get("error", {})
    if not isinstance(errors, dict):
        return set()
    return {e.get("reason") for e in errors.get("errors") or [] if isinstance(e, dict)}


def _google_http_error(exc: httpx.HTTPStatusError) -> HTTPException:
    """Map a Google API failure to an HTTP error without leaking internals."""
    status = exc.response.status_code
    if status == 401:
        return HTTPException(
            status_code=401,
            detail="Google token inválido o expirado — reconecta tu cuenta en Ajustes",
        )
    reasons = _google_error_reasons(exc)
    if "insufficientPermissions" in reasons:
        return HTTPException(
            status_code=403,
            detail="El token de Google no tiene permiso para Contacts — reconecta tu cuenta en Ajustes",
        )
    # Google reports optimistic-concurrency etag mismatches as 400 failedPrecondition.
    if "failedPrecondition" in reasons:
        return HTTPException(
            status_code=409,
            detail="El contacto cambió desde la última lectura — recarga e inténtalo de nuevo",
        )
    return HTTPException(status_code=status, detail="Google API error")


def _payload(body: ContactWriteIn) -> dict:
    """Only explicitly-set fields reach Google (PUT replace semantics)."""
    return body.model_dump(exclude_unset=True)


# ---------------------------------------------------------------------------
# Endpoints — declaration order matters: /status and /groups are literal
# paths and must precede the /{resource_name:path} catch-all.
# ---------------------------------------------------------------------------


@router.get("/status", response_model=ContactsStatusOut)
async def contacts_status(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Connection state plus contacts read/write scope capability."""
    can_read, can_write = gccs.contacts_capabilities(db)
    return {
        "connected": gts.is_connected(db),
        "contacts_read": can_read,
        "contacts_write": can_write,
    }


@router.get("/groups", response_model=ContactGroupListOut)
async def list_contact_groups(
    page_size: int = Query(default=100, ge=1, le=1000),
    page_token: str | None = Query(default=None, max_length=2048),
    google_token: str | None = Header(default=None, alias="X-Google-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List Google contact groups (``contactGroups/{id}`` resource names)."""
    access_token = await _read_token(google_token, db)
    try:
        return await gccs.list_contact_groups(access_token, page_size, page_token)
    except gccs.ContactsReconsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise _google_http_error(exc) from exc


@router.get("", response_model=ContactListOut)
@router.get("/", response_model=ContactListOut)
async def list_contacts(
    q: str | None = Query(default=None, max_length=256, description="Search query (people:searchContacts)"),
    query: str | None = Query(default=None, max_length=256, description="Alias for q"),
    group: str | None = Query(default=None, max_length=256, description="Filter by contactGroups/{id}"),
    page_size: int = Query(default=100, ge=1, le=1000),
    page_token: str | None = Query(default=None, max_length=2048),
    google_token: str | None = Header(default=None, alias="X-Google-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List contacts, optionally filtered by search query or contact group."""
    access_token = await _read_token(google_token, db)
    search = (q or query or "").strip() or None
    try:
        return await gccs.list_contacts(
            access_token,
            query=search,
            group=group,
            page_size=page_size,
            page_token=page_token,
        )
    except gccs.ContactsReconsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except gccs.ContactsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise _google_http_error(exc) from exc


@router.post("", response_model=ContactOut)
@router.post("/", response_model=ContactOut)
async def create_contact(
    body: ContactWriteIn,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Create a Google contact (requires the ``contacts`` write scope)."""
    access_token = await _write_token(db)
    try:
        return await gccs.create_contact(access_token, _payload(body))
    except gccs.ContactsReconsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except gccs.ContactsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise _google_http_error(exc) from exc


@router.get("/{resource_name:path}", response_model=ContactOut)
async def get_contact(
    resource_name: str,
    google_token: str | None = Header(default=None, alias="X-Google-Token"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Contact detail. ``resource_name`` is ``people/{id}`` (URL-encoded path)."""
    access_token = await _read_token(google_token, db)
    try:
        return await gccs.get_contact(access_token, resource_name)
    except gccs.ContactsReconsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except gccs.ContactsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise _google_http_error(exc) from exc


@router.put("/{resource_name:path}", response_model=ContactOut)
async def update_contact(
    resource_name: str,
    body: ContactWriteIn,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Update a contact — provided sections fully replace stored ones."""
    access_token = await _write_token(db)
    try:
        return await gccs.update_contact(access_token, resource_name, _payload(body), etag=body.etag)
    except gccs.ContactsReconsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except gccs.ContactsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise _google_http_error(exc) from exc


@router.delete("/{resource_name:path}")
async def delete_contact(
    resource_name: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Delete a contact."""
    access_token = await _write_token(db)
    try:
        await gccs.delete_contact(access_token, resource_name)
    except gccs.ContactsReconsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except gccs.ContactsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise _google_http_error(exc) from exc
    return {"status": "deleted", "resource_name": resource_name}
