"""Shared builder for httpx-family transport clients used by provider SDKs.

httpx-based SDKs default to ``trust_env=True``, which silently honors
ambient ``HTTP(S)_PROXY`` / ``ALL_PROXY`` variables — routing note content
and provider API keys through whatever proxy the environment defines
(#1330). All provider transports are therefore built with
``trust_env=False``. Deployments that legitimately need an egress proxy can
configure one explicitly via ``PROVIDER_PROXY_URL``.
"""

from collections.abc import Callable
from typing import Any

from config import settings


def build_async_http_client[T](factory: Callable[..., T], timeout: Any) -> T:
    """Build an async transport via ``factory`` with env-proxy trust disabled.

    ``factory`` is the SDK's own client constructor
    (``openai.DefaultAsyncHttpx2Client``) or a plain async client class
    (``httpx2.AsyncClient`` for anthropic, ``httpx.AsyncClient`` for
    cohere) — each SDK dictates which httpx-family transport it needs
    (openai/anthropic vendor the ``httpx2`` fork, cohere uses stock
    ``httpx``). All of them accept ``trust_env``/``timeout``/``proxy``
    kwargs.
    """
    kwargs: dict[str, Any] = {"trust_env": False, "timeout": timeout}
    if settings.provider_proxy_url:
        kwargs["proxy"] = settings.provider_proxy_url
    return factory(**kwargs)
