"""Shared OAuth browser-flow helpers for the integration routers (#1530).

The Google, Strava and Spotify ``GET /callback`` endpoints ran the same
~40-line flow copy-pasted: guard ``error``/``code``, verify the signed CSRF
``state``, exchange the code (mapping its two failure modes), persist the
tokens and answer the self-closing popup page — Strava and Spotify even
imported the Google router's *private* ``_callback_page``. This module is the
single implementation; each router supplies only its provider key, display
label, code-exchange callable and token-persistence callable.

It also hosts ``resolve_access_token`` — the header-override → stored-token →
401 resolution shared by the five integration routers (Google, Gmail and
Contacts via ``google_token_service``; Strava and Spotify via
``integration_token_service``).
"""

import html as html_module
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from services import oauth_state
from sqlalchemy.orm import Session

# The provider's code-exchange call: code → normalized token payload.
TokenExchange = Callable[[str], Awaitable[dict[str, Any]]]
# Persist the exchanged tokens for a provider: the DB write plus any
# best-effort provider call (e.g. Spotify's post-connect profile fetch).
TokenPersist = Callable[[Session, dict[str, Any]], Awaitable[None]]
# Resolve the stored, auto-refreshed access token for a provider.
StoredTokenResolver = Callable[[Session], Awaitable[str | None]]
# Extra gate on the stored-token path (e.g. Gmail/Contacts capability
# checks); raises HTTPException when the stored grant is under-scoped.
CapabilityCheck = Callable[[Session], None]


def callback_page(ok: bool, message: str, status_code: int = 200) -> HTMLResponse:
    """Minimal self-closing page for the popup opened by the settings panel."""
    icon = "OK" if ok else "ERROR"
    color = "#2e9e4f" if ok else "#c0392b"
    # Standard-library escaping (incl. quotes) for the text-node interpolation.
    safe = html_module.escape(message or "", quote=True)
    page = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Joidy</title></head>
<body style="font-family:system-ui;display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
<div style="text-align:center">
<p style="font-size:15px;color:{color};font-weight:600">{icon} — {safe}</p>
<p style="font-size:12px;color:#777">Puedes cerrar esta ventana.</p>
</div>
<script>setTimeout(function(){{ window.close(); }}, 1200);</script>
</body></html>"""
    return HTMLResponse(content=page, status_code=status_code)


async def run_callback(
    *,
    provider: str,
    provider_label: str,
    code: str,
    error: str,
    state: str,
    db: Session,
    exchange: TokenExchange,
    persist: TokenPersist,
) -> HTMLResponse:
    """Shared body of the public ``GET /callback`` endpoints.

    ``provider`` is the key the CSRF ``state`` was signed for;
    ``provider_label`` is the human name interpolated into the user-facing
    (Spanish) messages — every string is preserved verbatim from the
    per-router copies this replaces. Provider/HTTP details never reach the
    browser (CodeQL py/stack-trace-exposure).
    """
    if error:
        return callback_page(ok=False, message=f"Error de autorización con {provider_label}")
    if not code:
        return callback_page(ok=False, message="Falta el código de autorización")
    # CSRF gate (#1280/#1328): the state must be one this instance signed in
    # /auth. Verified before any token exchange so a forged callback cannot
    # bind an attacker's account here.
    if not oauth_state.verify_state(state, provider):
        return callback_page(ok=False, message="Estado OAuth inválido o expirado", status_code=403)

    try:
        tokens = await exchange(code)
    except httpx.HTTPStatusError:
        # No surface raw provider/HTTP details to the browser (CodeQL py/stack-trace-exposure)
        return callback_page(ok=False, message=f"Intercambio de token con {provider_label} falló")
    except RuntimeError:
        return callback_page(ok=False, message=f"{provider_label} OAuth no está configurado")

    await persist(db, tokens)
    return callback_page(ok=True, message=f"{provider_label} conectado")


async def resolve_access_token(
    db: Session,
    *,
    header_token: str | None,
    get_stored: StoredTokenResolver,
    not_connected_detail: str,
    check_capability: CapabilityCheck | None = None,
) -> str:
    """Resolve the effective access token: header override → stored → 401.

    An explicit ``X-*-Token`` header always wins (legacy contract — the
    override arrives by header only, never a query param, so credentials
    cannot leak into access logs, #1372/#1461). Otherwise the stored token
    is used (``get_stored`` refreshes transparently); a missing or failed
    one maps to 401 with the provider's own ``not_connected_detail``.
    ``check_capability`` — e.g. a Gmail/Contacts scope gate — runs only on
    the stored-token path, exactly like the per-router copies this replaces.
    """
    if header_token:
        return header_token
    token = await get_stored(db)
    if not token:
        raise HTTPException(status_code=401, detail=not_connected_detail)
    if check_capability is not None:
        check_capability(db)
    return token
