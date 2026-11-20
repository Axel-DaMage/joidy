"""``joidy auth`` — login/logout/status against ``/auth/login``."""

from __future__ import annotations

import sys
from typing import Annotated

import typer

from .. import client as client_mod
from .. import config, output
from ..options import ApiUrlOpt, Flags, JQOpt, JSONOpt, TokenOpt, YesOpt

auth_app = typer.Typer(help="Authenticate against the Joidy API.", no_args_is_help=True)


def do_login(client: client_mod.ApiClient, username: str, password: str) -> str:
    """Exchange credentials for a JWT. Returns the access token."""
    data = client.request("POST", "/auth/login", body={"username": username, "password": password})
    token = (data or {}).get("access_token") if isinstance(data, dict) else None
    if not token:
        raise client_mod.ApiError("login succeeded but no access_token in response", output.EXIT_SERVER)
    return token


def _read_stdin_once() -> str:
    return sys.stdin.read().rstrip("\n")


@auth_app.command("login")
def login(
    ctx: typer.Context,
    username: Annotated[str, typer.Option("--username", "-u", help="API username.")] = "user",
    password: Annotated[
        str | None,
        typer.Option("--password", "-p", help="API password; '-' reads it from stdin."),
    ] = None,
    save_url: Annotated[
        bool,
        typer.Option("--save-url/--no-save-url", help="Persist the resolved API URL alongside the token."),
    ] = True,
    json: JSONOpt = False,
    jq: JQOpt = None,
    yes: YesOpt = False,
    api_url: ApiUrlOpt = None,
    token: TokenOpt = None,
) -> None:
    """Log in and store the JWT in ~/.config/joidy/config.toml."""
    flags = Flags.make(ctx, json=json, jq=jq, yes=yes, api_url=api_url, token=token)

    if password == "-":
        password = _read_stdin_once()
    if password is None:
        if not sys.stdin.isatty():
            output.die("--password is required when stdin is not a TTY", output.EXIT_USAGE)
        password = typer.prompt("Password", hide_input=True)

    api_client = flags.client()
    try:
        access_token = do_login(api_client, username, password)
    except client_mod.ApiError as exc:
        output.die(str(exc), exc.exit_code)
        raise  # unreachable

    path = config.store_token(access_token, api_client.base_url if save_url else None)
    flags.emit(
        {
            "status": "ok",
            "api_url": api_client.base_url,
            "username": username,
            "credentials_file": str(path),
        }
    )


@auth_app.command("logout")
def logout(
    ctx: typer.Context,
    json: JSONOpt = False,
    jq: JQOpt = None,
    yes: YesOpt = False,
    api_url: ApiUrlOpt = None,
    token: TokenOpt = None,
) -> None:
    """Remove the stored token (env vars are unaffected)."""
    flags = Flags.make(ctx, json=json, jq=jq, yes=yes, api_url=api_url, token=token)
    path = config.clear_token()
    flags.emit({"status": "ok", "credentials_file": str(path), "token": None})


@auth_app.command("status")
def status(
    ctx: typer.Context,
    json: JSONOpt = False,
    jq: JQOpt = None,
    yes: YesOpt = False,
    api_url: ApiUrlOpt = None,
    token: TokenOpt = None,
) -> None:
    """Show the resolved API URL, token source, and server auth state."""
    flags = Flags.make(ctx, json=json, jq=jq, yes=yes, api_url=api_url, token=token)
    resolved_token, source = config.get_token(flags.token)
    api_client = flags.client()

    reachable = True
    auth_enabled = None
    try:
        probe = api_client.request("GET", "/auth/status")
        auth_enabled = probe.get("enabled") if isinstance(probe, dict) else None
    except client_mod.ApiError:
        reachable = False

    flags.emit(
        {
            "api_url": api_client.base_url,
            "reachable": reachable,
            "auth_enabled": auth_enabled,
            "token_source": source,
            "authenticated": resolved_token is not None,
            "credentials_file": str(config.config_path()),
        }
    )
