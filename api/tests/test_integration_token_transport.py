"""Credential-transport convention guard for the integrations routers (#1461).

OAuth access tokens must never travel in a query string — ``?token=`` URLs
leak credentials into access logs, proxies and browser history. The
Google-family routers honor an explicit token override via the
``X-Google-Token`` header only, mirroring the ``X-Spotify-Token`` /
``X-Strava-Token`` hardening (#1372).

These tests introspect the registered routes: they fail if any endpoint
re-introduces a ``token`` query parameter, and they pin the endpoints that
must accept the ``X-Google-Token`` header override.
"""

import inspect
from typing import Any

from fastapi.params import Header as HeaderParam
from fastapi.params import Query as QueryParam
from routers.integrations import contacts, github, gmail, google, spotify, strava

ALL_INTEGRATION_ROUTERS = (google.router, gmail.router, contacts.router, github.router, spotify.router, strava.router)

GOOGLE_TOKEN_HEADER = "X-Google-Token"

# Every Google-family route whose access-token override used to arrive via
# ``?token=`` — now resolved from ``X-Google-Token`` instead.
GOOGLE_HEADER_OVERRIDDEN_PATHS = {
    "/integrations/gmail/messages",
    "/integrations/gmail/messages/{message_id}",
    "/integrations/gmail/messages/{message_id}/attachments/{attachment_id}",
    "/integrations/gmail/history",
    "/integrations/contacts",
    "/integrations/contacts/",
    "/integrations/contacts/groups",
    "/integrations/contacts/{resource_name:path}",
    "/integrations/google/calendars",
    "/integrations/google/calendars/{calendar_id}/events",
    "/integrations/google/tasks",
    "/integrations/google/gmail",
    "/integrations/google/contacts",
}


def _route_params(route: Any) -> list[inspect.Parameter]:
    """Endpoint signature parameters for a registered route."""
    endpoint = getattr(route, "endpoint", None)
    if endpoint is None:
        return []
    return list(inspect.signature(endpoint).parameters.values())


def test_no_integration_endpoint_takes_token_query_param():
    """No endpoint may declare a ``token`` credential parameter that resolves
    from the query string — explicitly via ``Query(...)`` or implicitly via a
    bare scalar default. Header-bound params are the only allowed transport."""
    offenders: list[str] = []
    for router in ALL_INTEGRATION_ROUTERS:
        for route in router.routes:
            path = getattr(route, "path", "?")
            for param in _route_params(route):
                if param.name != "token":
                    continue
                default = param.default
                if isinstance(default, HeaderParam):
                    continue  # header transport — allowed
                if isinstance(default, QueryParam):
                    offenders.append(f"{path} ({param.name}=Query)")
                else:
                    offenders.append(f"{path} ({param.name} implicit query param)")
    assert offenders == []


def test_google_family_endpoints_accept_x_google_token_header():
    """Every endpoint that used to take ``?token=`` now declares the
    ``X-Google-Token`` header param."""
    found: set[str] = set()
    for router in (google.router, gmail.router, contacts.router):
        for route in router.routes:
            for param in _route_params(route):
                default = param.default
                if isinstance(default, HeaderParam) and default.alias == GOOGLE_TOKEN_HEADER:
                    found.add(getattr(route, "path", "?"))
    missing = GOOGLE_HEADER_OVERRIDDEN_PATHS - found
    assert not missing, f"endpoints missing the {GOOGLE_TOKEN_HEADER} header param: {sorted(missing)}"


def test_google_family_declares_single_shared_header_name():
    """The override header name is ``X-Google-Token`` everywhere — one shared
    convention, not per-endpoint spellings."""
    aliases: set[str] = set()
    for router in (google.router, gmail.router, contacts.router):
        for route in router.routes:
            for param in _route_params(route):
                default = param.default
                if isinstance(default, HeaderParam) and default.alias and "token" in default.alias.lower():
                    aliases.add(default.alias)
    assert aliases == {GOOGLE_TOKEN_HEADER}
