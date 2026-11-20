"""Thin HTTP client for the Joidy API.

Talks to ``JOIDY_API_URL`` (default ``http://localhost:8000``) with
``Authorization: Bearer <token>`` — identical behaviour against the local
dev stack, the Docker install, or a remote instance.
"""

from __future__ import annotations

from typing import Any

import httpx

from . import config, output
from .output import EXIT_AUTH, EXIT_ERROR, EXIT_NOT_FOUND, EXIT_SERVER, EXIT_USAGE


class ApiError(Exception):
    """An API call failed. ``exit_code`` follows the documented convention."""

    def __init__(self, message: str, exit_code: int = EXIT_ERROR, status: int | None = None):
        super().__init__(message)
        self.exit_code = exit_code
        self.status = status


_STATUS_EXIT = {
    400: EXIT_USAGE,
    401: EXIT_AUTH,
    403: EXIT_AUTH,
    404: EXIT_NOT_FOUND,
    422: EXIT_USAGE,
}


class ApiClient:
    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        *,
        timeout: float = 15.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._http = httpx.Client(base_url=self.base_url, timeout=timeout, transport=transport)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        try:
            response = self._http.request(method, path, params=params, json=body, headers=headers)
        except httpx.TimeoutException:
            raise ApiError(f"request to {self.base_url} timed out", EXIT_SERVER) from None
        except httpx.HTTPError as exc:
            raise ApiError(f"cannot reach Joidy API at {self.base_url}: {exc}", EXIT_SERVER) from None

        if response.status_code >= 400:
            self._raise_for_status(response)
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    def _raise_for_status(self, response: httpx.Response) -> None:
        detail = _extract_detail(response)
        status = response.status_code
        code = _STATUS_EXIT.get(status, EXIT_SERVER if status >= 500 else EXIT_ERROR)
        message = f"API {status} on {response.request.method} {response.request.url.path}: {detail}"
        if code == EXIT_AUTH:
            message += " — run `joidy auth login` or set JOIDY_TOKEN"
        raise ApiError(message, code, status=status)


def _extract_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:300] or response.reason_phrase
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
        if isinstance(detail, list):  # FastAPI validation errors
            return "; ".join(str(item.get("msg", item)) for item in detail[:5])
    return str(payload)[:300]


def create(api_url: str | None = None, token: str | None = None) -> ApiClient:
    """Build a client from flag > env > stored config resolution order."""
    url = config.get_api_url(api_url)
    resolved_token, _source = config.get_token(token)
    return ApiClient(url, resolved_token)


def call(client: ApiClient, method: str, path: str, **kwargs: Any) -> Any:
    """Perform a request or exit with the documented error code."""
    try:
        return client.request(method, path, **kwargs)
    except ApiError as exc:
        output.die(str(exc), exc.exit_code)
        raise  # unreachable; satisfies type-checkers
