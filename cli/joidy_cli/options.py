"""Shared CLI option declarations and per-invocation flag bundle.

Every data-plane command accepts the same trailing options so agents can
rely on a uniform surface:

    joidy notes new --title T --content - --json --yes

The same flags also work at the root level (``joidy --json notes ls``) via
``ctx.obj``; command-level flags win when both are given.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

import typer

from . import client as client_mod
from . import output

JSONOpt = Annotated[bool, typer.Option("--json", help="Emit raw JSON output.")]
JQOpt = Annotated[
    str | None,
    typer.Option("--jq", help="JMESPath expression applied to the output (e.g. '[].id')."),
]
YesOpt = Annotated[
    bool,
    typer.Option("--yes", "-y", help="Skip confirmation prompts (required for destructive ops when non-interactive)."),
]
ApiUrlOpt = Annotated[
    str | None,
    typer.Option("--api-url", help="Joidy API base URL (overrides JOIDY_API_URL and stored config)."),
]
TokenOpt = Annotated[
    str | None,
    typer.Option("--token", help="Bearer token (overrides JOIDY_TOKEN and stored credentials)."),
]


@dataclass
class Flags:
    json: bool = False
    jq: str | None = None
    yes: bool = False
    api_url: str | None = None
    token: str | None = None

    @classmethod
    def make(
        cls,
        ctx: typer.Context,
        *,
        json: bool = False,
        jq: str | None = None,
        yes: bool = False,
        api_url: str | None = None,
        token: str | None = None,
    ) -> Flags:
        global_opts: dict[str, Any] = ctx.obj or {}
        return cls(
            json=json or global_opts.get("json", False),
            jq=jq if jq is not None else global_opts.get("jq"),
            yes=yes or global_opts.get("yes", False),
            api_url=api_url or global_opts.get("api_url"),
            token=token or global_opts.get("token"),
        )

    def emit(self, data: Any) -> None:
        output.emit(data, json_mode=self.json, jq=self.jq)

    def client(self) -> client_mod.ApiClient:
        return client_mod.create(api_url=self.api_url, token=self.token)
