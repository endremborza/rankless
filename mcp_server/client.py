"""Async HTTP client for the rankless backend."""

from typing import Any

import httpx

import mcp_server

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    # Base URL is read at build time from the (mutable) module global so an
    # in-process caller can retarget the backend via mcp_server.set_backend().
    global _client
    if _client is None:
        _client = httpx.AsyncClient(base_url=mcp_server.BE_URL, timeout=30.0)
    return _client


def reset() -> None:
    """Drop the cached client so the next call rebuilds against `BE_URL`."""
    global _client
    _client = None


async def get_json(path: str, params: dict | None = None):
    return (await get_with_headers(path, params))[0]


async def get_with_headers(
    path: str, params: dict | None = None
) -> tuple[Any, httpx.Headers]:
    """The JSON body and the response headers, for the endpoints that carry
    counts in headers (`/slice`)."""
    clean = {k: v for k, v in (params or {}).items() if v is not None}
    resp = await get_client().get(path, params=clean)
    resp.raise_for_status()
    return resp.json(), resp.headers


async def aclose() -> None:
    """Dispose the client; needed when a caller runs multiple event loops."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
