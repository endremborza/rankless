"""Async HTTP client for the rankless backend."""

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


def unreachable(url: object, exc: Exception) -> str:
    return f"backend unreachable at {url}: {exc!r}"


async def get_json(path: str, params: dict | None = None):
    """A 4xx raises `ValueError` carrying the backend's body, the refusal text the
    model reads (the MCP SDK reports a tool's exception as its message); a backend
    that does not answer raises `ConnectionError` saying so."""
    clean = {k: v for k, v in (params or {}).items() if v is not None}
    try:
        resp = await get_client().get(path, params=clean)
    except httpx.TransportError as exc:
        raise ConnectionError(unreachable(exc.request.url, exc)) from exc
    if resp.is_client_error:
        raise ValueError(f"{resp.status_code} {path}: {resp.text}")
    resp.raise_for_status()
    return resp.json()


async def aclose() -> None:
    """Dispose the client; needed when a caller runs multiple event loops."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
