"""Gmail API service (#42).

Business logic for the dedicated ``/integrations/gmail`` router: OAuth-scope
capability checks, Gmail message normalization to snake_case, RFC822
composition for ``messages.send``, attachment decoding and ``users.watch``
state persistence.

Scope model mirrors ``google_contacts_service``: reads work with
``gmail.readonly`` (or the broader ``gmail.modify``/``gmail.compose``/full
mail scope); label mutations need ``gmail.modify``; sending needs
``gmail.send``/``gmail.modify``/``gmail.compose``. Tokens granted before the
scope bump provably lacking a capability are rejected up front with
``GmailReconsentRequired`` (→ HTTP 403); Google-side
``insufficientPermissions`` responses map the same way.
"""

import base64
import binascii
import json
import re
from collections.abc import Iterator
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import format_datetime
from typing import Any, NoReturn

import httpx
from config import settings
from models.google_token import GoogleToken
from repositories import ConfigRepository
from services import google_service as gs
from services.google_token_service import get_stored_token
from sqlalchemy.orm import Session

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_MODIFY_SCOPE = "https://www.googleapis.com/auth/gmail.modify"
GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GMAIL_COMPOSE_SCOPE = "https://www.googleapis.com/auth/gmail.compose"
# Full-mailbox scope grants everything below.
GMAIL_FULL_SCOPE = "https://mail.google.com/"

_READ_SCOPES = frozenset({GMAIL_READONLY_SCOPE, GMAIL_MODIFY_SCOPE, GMAIL_COMPOSE_SCOPE, GMAIL_FULL_SCOPE})
_MODIFY_SCOPES = frozenset({GMAIL_MODIFY_SCOPE, GMAIL_FULL_SCOPE})
_SEND_SCOPES = frozenset({GMAIL_SEND_SCOPE, GMAIL_MODIFY_SCOPE, GMAIL_COMPOSE_SCOPE, GMAIL_FULL_SCOPE})

# system_config key holding the last users.watch registration (JSON). Lives
# outside user_settings:* so it can never collide with client-chosen keys.
_WATCH_STATE_KEY = "gmail_watch_state"

# Gmail resource ids are URL-safe tokens; the charset also blocks path
# traversal into other Gmail endpoints when interpolated into request URLs.
_GMAIL_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_LABEL_ID_RE = re.compile(r"^[A-Za-z0-9_]{1,128}$")
_HISTORY_ID_RE = re.compile(r"^\d{1,20}$")
_ADDR_SPEC_RE = re.compile(r"^[^\s@<>,;]+@[^\s@<>,;]+$")
_MIME_TOKEN_RE = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")

# Gmail system labels used by the label actions.
LABEL_INBOX = "INBOX"
LABEL_TRASH = "TRASH"
LABEL_UNREAD = "UNREAD"

MAX_TOTAL_RECIPIENTS = 50
MAX_ATTACHMENTS = 10
# Per-attachment decoded cap for outgoing mail (Gmail's own message limit is
# ~25 MiB; we stay well under it so base64 overhead never trips the API).
MAX_OUT_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_OUT_ATTACHMENTS_TOTAL_BYTES = 20 * 1024 * 1024
MAX_OUT_ATTACHMENT_B64_CHARS = 14_000_000
# Incoming attachment download cap — keeps a single JSON response bounded.
MAX_IN_ATTACHMENT_BYTES = 20 * 1024 * 1024
MAX_IN_ATTACHMENT_B64_CHARS = 28_000_000
# Body extraction caps: bound decode work and the JSON payload size.
MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_BODY_CHARS = 500_000


class GmailReconsentRequired(RuntimeError):
    """The stored Google token lacks the Gmail scope an operation needs."""


class GmailValidationError(ValueError):
    """Invalid client input for the Gmail API (→ HTTP 400)."""


class GmailPayloadTooLarge(GmailValidationError):
    """Decoded payload exceeds the configured size cap (→ HTTP 413)."""


class GmailWatchNotConfigured(RuntimeError):
    """users.watch needs GOOGLE_GMAIL_PUBSUB_TOPIC, which is not set."""


# ---------------------------------------------------------------------------
# Scope capabilities
# ---------------------------------------------------------------------------


def _granted_scopes(row: GoogleToken | None) -> set[str] | None:
    """Space-separated OAuth scopes granted to the stored token.

    Returns None when unknown (no row or legacy row without a scope string) —
    callers must not treat unknown as denied.
    """
    if row is None or not row.scope:
        return None
    return set(row.scope.split())


def gmail_capabilities(db: Session) -> dict[str, bool | None]:
    """``{read, modify, send}`` capability flags; None entries mean 'unknown'."""
    scopes = _granted_scopes(get_stored_token(db))
    if scopes is None:
        return {"read": None, "modify": None, "send": None}
    return {
        "read": bool(scopes & _READ_SCOPES),
        "modify": bool(scopes & _MODIFY_SCOPES),
        "send": bool(scopes & _SEND_SCOPES),
    }


_CAPABILITY_LABELS = {
    "read": "lectura",
    "modify": "modificación de etiquetas",
    "send": "envío",
}


def require_capability(db: Session, capability: str) -> None:
    """Raise GmailReconsentRequired when the stored grant provably lacks the
    capability. Unknown scopes are left to Google's 403 mapping."""
    allowed = gmail_capabilities(db).get(capability)
    if allowed is False:
        label = _CAPABILITY_LABELS.get(capability, capability)
        raise GmailReconsentRequired(
            f"El token de Google no tiene permiso de {label} en Gmail. "
            "Reconecta tu cuenta en Ajustes para habilitar esta función."
        )


def _reconsent_if_needed(exc: httpx.HTTPStatusError) -> NoReturn:
    """Raise GmailReconsentRequired on 403 insufficientPermissions, else re-raise."""
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
                raise GmailReconsentRequired(
                    "El token de Google no tiene permiso para Gmail. Reconecta tu cuenta en Ajustes."
                ) from exc
    raise exc


# ---------------------------------------------------------------------------
# Id / label / query validation
# ---------------------------------------------------------------------------


def validate_gmail_id(value: str, kind: str = "message") -> str:
    """Accept only URL-safe Gmail resource ids — nothing else may reach the
    Gmail API path (no traversal into other endpoints)."""
    if not _GMAIL_ID_RE.match(value):
        raise GmailValidationError(f"Invalid Gmail {kind} id")
    return value


def validate_label_ids(values: list[str]) -> list[str]:
    """Validate a list of Gmail label ids (system labels or ``Label_N``)."""
    out: list[str] = []
    for value in values:
        candidate = value.strip()
        if not _LABEL_ID_RE.match(candidate):
            raise GmailValidationError(f"Invalid Gmail label id: {value!r}")
        out.append(candidate)
    return out


def validate_history_id(value: str) -> str:
    """historyIds are int64 rendered as decimal strings."""
    candidate = value.strip()
    if not _HISTORY_ID_RE.match(candidate):
        raise GmailValidationError("Invalid Gmail history id")
    return candidate


def _since_to_epoch(value: str) -> int:
    """Convert a ``since`` filter to unix seconds for Gmail's ``after:``.

    Accepts epoch seconds/milliseconds or an ISO-8601 datetime.
    """
    v = value.strip()
    if re.fullmatch(r"\d{9,13}(\.\d+)?", v):
        epoch = float(v)
        if epoch > 1e12:  # milliseconds → seconds
            epoch /= 1000
        return int(epoch)
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GmailValidationError("since: formato inválido (usa epoch o ISO-8601)") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp())


def _build_list_query(q: str | None, since: str | None) -> str | None:
    """Compose the Gmail search query from ``q`` and the ``since`` filter."""
    parts: list[str] = []
    if q and q.strip():
        parts.append(q.strip())
    if since and since.strip():
        parts.append(f"after:{_since_to_epoch(since)}")
    return " ".join(parts) or None


def _ms_to_iso(value: Any) -> str | None:
    """Gmail renders epoch-millis fields as strings; expose ISO-8601."""
    try:
        return datetime.fromtimestamp(int(str(value)) / 1000, tz=UTC).isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return None


# ---------------------------------------------------------------------------
# Normalization — Gmail resources → snake_case dicts for the frontend
# ---------------------------------------------------------------------------


def _header_map(payload: dict[str, Any]) -> dict[str, str]:
    """Lowercased header name → value (first occurrence wins)."""
    headers: dict[str, str] = {}
    for item in payload.get("headers") or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip().lower()
        value = item.get("value")
        if name and value is not None and name not in headers:
            headers[name] = str(value)
    return headers


_OUTBOUND_HEADERS = ("from", "to", "cc", "bcc", "subject", "date", "message_id", "reply_to", "in_reply_to")


def _walk_parts(payload: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Depth-first walk over a MIME payload tree (payload + nested parts)."""
    yield payload
    for part in payload.get("parts") or []:
        if isinstance(part, dict):
            yield from _walk_parts(part)


def _part_charset(part: dict[str, Any]) -> str:
    """Charset declared on the part's Content-Type header, else utf-8."""
    for item in part.get("headers") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("name") or "").strip().lower() == "content-type":
            match = re.search(r'charset="?([^";\s]+)"?', str(item.get("value") or ""), re.IGNORECASE)
            if match:
                return match.group(1)
    return "utf-8"


def _decode_base64url_lenient(data: str) -> bytes:
    """base64url → bytes; malformed upstream data decodes to b'' instead of
    failing the whole message read."""
    try:
        normalized = "".join(str(data).split()).replace("-", "+").replace("_", "/")
        normalized += "=" * (-len(normalized) % 4)
        return base64.b64decode(normalized, validate=False)
    except (binascii.Error, ValueError):
        return b""


def _decode_part_text(part: dict[str, Any]) -> tuple[str, bool]:
    """Decode a text/* MIME part body; returns (text, truncated)."""
    data = str((part.get("body") or {}).get("data") or "")
    raw = _decode_base64url_lenient(data)
    truncated = False
    if len(raw) > MAX_BODY_BYTES:
        raw = raw[:MAX_BODY_BYTES]
        truncated = True
    try:
        text = raw.decode(_part_charset(part), errors="replace")
    except (LookupError, ValueError):
        text = raw.decode("utf-8", errors="replace")
    if len(text) > MAX_BODY_CHARS:
        text = text[:MAX_BODY_CHARS]
        truncated = True
    return text, truncated


def _extract_bodies(payload: dict[str, Any]) -> tuple[str | None, str | None, bool]:
    """First text/plain and text/html bodies in the MIME tree."""
    text_body: str | None = None
    html_body: str | None = None
    truncated = False
    for part in _walk_parts(payload):
        body = part.get("body") or {}
        filename = part.get("filename") or ""
        # Attachment parts carry attachmentId (or inline data) — never bodies.
        if filename or body.get("attachmentId"):
            continue
        if not body.get("data"):
            continue
        mime = str(part.get("mimeType") or "").lower()
        if mime == "text/plain" and text_body is None:
            text_body, t = _decode_part_text(part)
            truncated = truncated or t
        elif mime == "text/html" and html_body is None:
            html_body, t = _decode_part_text(part)
            truncated = truncated or t
    return text_body, html_body, truncated


def _extract_attachments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Attachment metadata for every MIME part that carries an attachmentId."""
    out: list[dict[str, Any]] = []
    for part in _walk_parts(payload):
        body = part.get("body") or {}
        attachment_id = body.get("attachmentId")
        if not attachment_id:
            continue
        filename = part.get("filename") or ""
        out.append(
            {
                "attachment_id": attachment_id,
                "filename": filename or None,
                "mime_type": part.get("mimeType") or "application/octet-stream",
                "size": body.get("size"),
                "part_id": part.get("partId"),
            }
        )
    return out


def normalize_message_summary(message: dict[str, Any]) -> dict[str, Any]:
    """Flatten a messages.list stub (or any Message resource) for list views."""
    return {
        "id": message.get("id"),
        "thread_id": message.get("threadId"),
        "label_ids": message.get("labelIds") or [],
        "snippet": message.get("snippet"),
        "internal_date": _ms_to_iso(message.get("internalDate")),
        "size_estimate": message.get("sizeEstimate"),
        "history_id": message.get("historyId"),
    }


def normalize_message(message: dict[str, Any]) -> dict[str, Any]:
    """Flatten a format=full Message resource: headers, bodies, attachments."""
    payload = message.get("payload") or {}
    headers = _header_map(payload)
    text_body, html_body, truncated = _extract_bodies(payload)
    out: dict[str, Any] = normalize_message_summary(message)
    out["headers"] = {name: headers[name] for name in _OUTBOUND_HEADERS if name in headers}
    out["body_text"] = text_body
    out["body_html"] = html_body
    out["body_truncated"] = truncated
    out["attachments"] = _extract_attachments(payload)
    return out


def normalize_send_result(message: dict[str, Any]) -> dict[str, Any]:
    """Compact result for messages.send — id/thread/labels only."""
    return {
        "id": message.get("id"),
        "thread_id": message.get("threadId"),
        "label_ids": message.get("labelIds") or [],
    }


def _norm_history_message_ref(item: Any) -> dict[str, Any]:
    msg = item.get("message") if isinstance(item, dict) else None
    msg = msg if isinstance(msg, dict) else {}
    return {
        "id": msg.get("id"),
        "thread_id": msg.get("threadId"),
        "label_ids": msg.get("labelIds") or [],
    }


def _norm_label_change(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"message_id": None, "label_ids": []}
    raw_msg = item.get("message")
    msg = raw_msg if isinstance(raw_msg, dict) else {}
    return {
        "message_id": msg.get("id"),
        "label_ids": item.get("labelIds") or [],
    }


def normalize_history(data: dict[str, Any]) -> dict[str, Any]:
    """Flatten users.history.list records for incremental sync clients."""
    records: list[dict[str, Any]] = []
    for record in data.get("history") or []:
        if not isinstance(record, dict):
            continue
        records.append(
            {
                "id": record.get("id"),
                "messages_added": [_norm_history_message_ref(m) for m in record.get("messagesAdded") or []],
                "messages_deleted": [_norm_history_message_ref(m) for m in record.get("messagesDeleted") or []],
                "labels_added": [_norm_label_change(m) for m in record.get("labelsAdded") or []],
                "labels_removed": [_norm_label_change(m) for m in record.get("labelsRemoved") or []],
            }
        )
    return {
        "history_id": data.get("historyId"),
        "next_page_token": data.get("nextPageToken"),
        "records": records,
    }


# ---------------------------------------------------------------------------
# Read orchestration
# ---------------------------------------------------------------------------


async def list_messages(
    token: str,
    *,
    q: str | None = None,
    since: str | None = None,
    label_ids: list[str] | None = None,
    max_results: int = 50,
    page_token: str | None = None,
) -> dict[str, Any]:
    """One page of message stubs. ``since`` becomes an ``after:<epoch>``
    clause so polling clients can fetch only newer mail."""
    params: dict[str, Any] = {"maxResults": max_results}
    query = _build_list_query(q, since)
    if query:
        params["q"] = query
    if page_token:
        params["pageToken"] = page_token
    if label_ids:
        params["labelIds"] = validate_label_ids(label_ids)
    try:
        data = await gs.list_gmail_messages_raw(token, params)
    except httpx.HTTPStatusError as exc:
        _reconsent_if_needed(exc)
    return {
        "messages": [normalize_message_summary(m) for m in data.get("messages") or [] if isinstance(m, dict)],
        "next_page_token": data.get("nextPageToken"),
        "result_size_estimate": data.get("resultSizeEstimate"),
    }


async def get_message(token: str, message_id: str) -> dict[str, Any]:
    """Full message: headers, text/html bodies and attachment metadata."""
    message_id = validate_gmail_id(message_id)
    try:
        message = await gs.get_gmail_message_raw(token, message_id)
    except httpx.HTTPStatusError as exc:
        _reconsent_if_needed(exc)
    return normalize_message(message)


async def get_attachment(token: str, message_id: str, attachment_id: str) -> dict[str, Any]:
    """Decode one attachment; returns standard base64 for JSON transport."""
    message_id = validate_gmail_id(message_id)
    attachment_id = validate_gmail_id(attachment_id, kind="attachment")
    try:
        data = await gs.get_gmail_attachment(token, message_id, attachment_id)
    except httpx.HTTPStatusError as exc:
        _reconsent_if_needed(exc)
    raw = str(data.get("data") or "")
    if len(raw) > MAX_IN_ATTACHMENT_B64_CHARS:
        raise GmailPayloadTooLarge("El adjunto excede el tamaño máximo permitido")
    try:
        normalized = "".join(raw.split()).replace("-", "+").replace("_", "/")
        normalized += "=" * (-len(normalized) % 4)
        decoded = base64.b64decode(normalized, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise GmailValidationError("Gmail devolvió datos de adjunto inválidos") from exc
    if len(decoded) > MAX_IN_ATTACHMENT_BYTES:
        raise GmailPayloadTooLarge("El adjunto excede el tamaño máximo permitido")
    return {
        "attachment_id": attachment_id,
        "size": len(decoded),
        "data_base64": base64.b64encode(decoded).decode("ascii"),
    }


async def get_history(
    token: str,
    *,
    start_history_id: str,
    page_token: str | None = None,
    max_results: int = 100,
    label_id: str | None = None,
) -> dict[str, Any]:
    """Incremental mailbox changes since ``startHistoryId`` (polling path that
    complements users.watch push notifications)."""
    params: dict[str, Any] = {
        "startHistoryId": validate_history_id(start_history_id),
        "maxResults": max_results,
    }
    if page_token:
        params["pageToken"] = page_token
    if label_id:
        params["labelId"] = validate_label_ids([label_id])[0]
    try:
        data = await gs.list_gmail_history(token, params)
    except httpx.HTTPStatusError as exc:
        _reconsent_if_needed(exc)
    return normalize_history(data)


# ---------------------------------------------------------------------------
# Label mutations (archive / trash / unread …)
# ---------------------------------------------------------------------------


async def modify_labels(
    token: str,
    message_id: str,
    *,
    add: list[str] | None = None,
    remove: list[str] | None = None,
) -> dict[str, Any]:
    """users.messages.modify — returns the updated message summary."""
    message_id = validate_gmail_id(message_id)
    add_ids = validate_label_ids(add or [])
    remove_ids = validate_label_ids(remove or [])
    if not add_ids and not remove_ids:
        raise GmailValidationError("No label changes requested")
    try:
        message = await gs.modify_gmail_message_labels(token, message_id, add_ids, remove_ids)
    except httpx.HTTPStatusError as exc:
        _reconsent_if_needed(exc)
    return normalize_message_summary(message)


# ---------------------------------------------------------------------------
# Send — RFC822 composition
# ---------------------------------------------------------------------------


def _clean_header(value: str | None) -> str:
    """Collapse whitespace/control chars — RFC822 header injection guard."""
    if value is None:
        return ""
    return re.sub(r"[\x00-\x1f\x7f]+", " ", str(value)).strip()


def _parse_recipients(value: str | None, field: str) -> list[str]:
    """Comma-separated addresses → validated tokens for a To/Cc/Bcc header.

    Accepts plain ``user@domain`` entries and ``Display Name <user@domain>``;
    the addr-spec inside ``<>`` is what gets validated.
    """
    if not value:
        return []
    addresses: list[str] = []
    for token in _clean_header(value).split(","):
        token = token.strip()
        if not token:
            continue
        candidate = token
        if "<" in token and ">" in token:
            candidate = token[token.index("<") + 1 : token.rindex(">")].strip()
        if candidate.count("@") != 1 or not _ADDR_SPEC_RE.match(candidate):
            raise GmailValidationError(f"Dirección de correo inválida en {field}")
        addresses.append(token)
    return addresses


def _decode_out_attachment(value: str, filename: str) -> bytes:
    """Decode client-supplied base64 attachment data with size caps."""
    raw = str(value or "")
    if len(raw) > MAX_OUT_ATTACHMENT_B64_CHARS:
        raise GmailValidationError(f"{filename}: adjunto demasiado grande")
    try:
        normalized = "".join(raw.split()).replace("-", "+").replace("_", "/")
        normalized += "=" * (-len(normalized) % 4)
        decoded = base64.b64decode(normalized, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise GmailValidationError(f"{filename}: datos base64 inválidos") from exc
    if len(decoded) > MAX_OUT_ATTACHMENT_BYTES:
        raise GmailValidationError(
            f"{filename}: adjunto demasiado grande (máx. {MAX_OUT_ATTACHMENT_BYTES // (1024 * 1024)} MiB)"
        )
    return decoded


def _prepare_attachments(attachments: list[dict[str, Any]] | None) -> list[tuple[str, str, bytes]]:
    """Validate + decode outgoing attachments; returns (filename, ctype, bytes)."""
    items = attachments or []
    if len(items) > MAX_ATTACHMENTS:
        raise GmailValidationError(f"Demasiados adjuntos (máx. {MAX_ATTACHMENTS})")
    prepared: list[tuple[str, str, bytes]] = []
    total = 0
    for item in items:
        if not isinstance(item, dict):
            raise GmailValidationError("Adjunto inválido")
        filename = _clean_header(str(item.get("filename") or "")) or "attachment"
        # Flatten path separators — a filename is a MIME parameter, not a path.
        filename = filename.replace("/", "_").replace("\\", "_")[:255]
        content_type = _clean_header(str(item.get("content_type") or "application/octet-stream"))
        maintype, _, subtype = content_type.partition("/")
        if not (_MIME_TOKEN_RE.fullmatch(maintype) and _MIME_TOKEN_RE.fullmatch(subtype)):
            maintype, subtype = "application", "octet-stream"
        data = _decode_out_attachment(str(item.get("data_base64") or ""), filename)
        total += len(data)
        if total > MAX_OUT_ATTACHMENTS_TOTAL_BYTES:
            raise GmailValidationError("El tamaño total de los adjuntos excede el máximo permitido")
        prepared.append((filename, f"{maintype}/{subtype}", data))
    return prepared


def build_rfc822(
    *,
    to: list[str],
    cc: list[str],
    bcc: list[str],
    subject: str,
    body: str,
    body_html: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
) -> str:
    """Compose an RFC822 message and return base64url (no padding) for
    ``users.messages.send``. ``email.message.EmailMessage`` handles RFC2047
    header encoding, MIME-Version and multipart/alternative assembly."""
    msg = EmailMessage()
    msg["Date"] = format_datetime(datetime.now(UTC))
    if to:
        msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    if bcc:
        msg["Bcc"] = ", ".join(bcc)
    subject_clean = _clean_header(subject)
    if subject_clean:
        msg["Subject"] = subject_clean

    if body_html:
        msg.set_content(body or "")
        msg.add_alternative(body_html, subtype="html")
    else:
        msg.set_content(body or "")

    for filename, content_type, data in _prepare_attachments(attachments):
        maintype, _, subtype = content_type.partition("/")
        try:
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)
        except ValueError as exc:
            raise GmailValidationError(f"{filename}: tipo de contenido inválido") from exc

    return base64.urlsafe_b64encode(msg.as_bytes()).rstrip(b"=").decode("ascii")


async def send_message(token: str, data: dict[str, Any]) -> dict[str, Any]:
    """Build the RFC822 payload and send via users.messages.send."""
    to = _parse_recipients(data.get("to"), "to")
    cc = _parse_recipients(data.get("cc"), "cc")
    bcc = _parse_recipients(data.get("bcc"), "bcc")
    if len(to) + len(cc) + len(bcc) > MAX_TOTAL_RECIPIENTS:
        raise GmailValidationError(f"Demasiados destinatarios (máx. {MAX_TOTAL_RECIPIENTS})")
    if not (to or cc or bcc):
        raise GmailValidationError("Se requiere al menos un destinatario (to, cc o bcc)")
    body = str(data.get("body") or "")
    body_html = data.get("body_html")
    body_html = str(body_html) if body_html else None
    if not body.strip() and not (body_html and body_html.strip()):
        raise GmailValidationError("El correo no puede estar vacío")

    raw = build_rfc822(
        to=to,
        cc=cc,
        bcc=bcc,
        subject=str(data.get("subject") or ""),
        body=body,
        body_html=body_html,
        attachments=data.get("attachments"),
    )
    try:
        sent = await gs.send_gmail_message(token, raw)
    except httpx.HTTPStatusError as exc:
        _reconsent_if_needed(exc)
    return normalize_send_result(sent)


# ---------------------------------------------------------------------------
# users.watch — Pub/Sub push registration (state persisted in system_config)
# ---------------------------------------------------------------------------


def _pubsub_topic() -> str:
    return (settings.google_gmail_pubsub_topic or "").strip()


def watch_configured() -> bool:
    """True when GOOGLE_GMAIL_PUBSUB_TOPIC names a Pub/Sub topic."""
    return bool(_pubsub_topic())


def get_watch_state(db: Session) -> dict[str, Any] | None:
    """Last successful users.watch registration, or None."""
    raw = ConfigRepository(db).get(_WATCH_STATE_KEY)
    if not raw:
        return None
    try:
        state = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return state if isinstance(state, dict) else None


def _save_watch_state(db: Session, state: dict[str, Any]) -> None:
    ConfigRepository(db).set(_WATCH_STATE_KEY, json.dumps(state))
    db.commit()


def _clear_watch_state(db: Session) -> None:
    ConfigRepository(db).set(_WATCH_STATE_KEY, "")
    db.commit()


async def register_watch(db: Session, token: str, label_ids: list[str] | None = None) -> dict[str, Any]:
    """Register users.watch against the configured Pub/Sub topic and persist
    the returned historyId/expiration so clients can poll /history from it."""
    topic = _pubsub_topic()
    if not topic:
        raise GmailWatchNotConfigured(
            "Gmail push no está configurado — define GOOGLE_GMAIL_PUBSUB_TOPIC "
            "(projects/<proyecto>/topics/<topic>) para habilitar users.watch"
        )
    labels = validate_label_ids(label_ids or [])
    try:
        data = await gs.watch_gmail_mailbox(token, topic, labels or None)
    except httpx.HTTPStatusError as exc:
        _reconsent_if_needed(exc)
    state = {
        "topic_name": topic,
        "history_id": data.get("historyId"),
        "expiration": _ms_to_iso(data.get("expiration")),
        "registered_at": datetime.now(UTC).isoformat(),
    }
    _save_watch_state(db, state)
    return state


async def stop_watch(db: Session, token: str) -> dict[str, Any]:
    """users.stop — halt push notifications and clear the stored state."""
    try:
        await gs.stop_gmail_watch(token)
    except httpx.HTTPStatusError as exc:
        _reconsent_if_needed(exc)
    _clear_watch_state(db)
    return {"status": "stopped"}
