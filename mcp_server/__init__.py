"""MCP proxy exposing the rankless backend to any MCP client.

A thin Python process that
proxies tool calls to the low-latency Rust backend, shapes responses for
agents (flatten trees, truncate, attach rankless.org backlinks), and keeps
rate/agent logic out of the data hot path.

Run over stdio with `uv run -m mcp_server`.
"""

import os
from urllib.parse import quote

BACKENDS = {
    "local": "http://127.0.0.1:3038/v1",
    "alpha": "https://alpha-api.rankless.org/v1",
    "live": "https://api.rankless.org/v1",
}
BE_URL = os.environ.get("RANKLESS_BE_URL", BACKENDS["local"])


def resolve_backend(arg: str) -> tuple[str, str]:
    """(`/v1` base URL, label) for a `BACKENDS` key or an explicit http(s) URL."""
    if arg in BACKENDS:
        return BACKENDS[arg], arg
    if arg.startswith("http"):
        return arg.rstrip("/"), "custom"
    raise SystemExit(f"backend must be one of {list(BACKENDS)} or an http(s) URL.")


SITE_URL = os.environ.get("RANKLESS_SITE_URL", "https://rankless.org")

ROOT_TYPES = ("authors", "institutions", "sources", "countries", "subfields")
SEARCH_TYPES = (*ROOT_TYPES, "all")


# JS encodeURIComponent's unreserved set, so an id encodes to the same bytes here
# as in the frontend and both produce the site's canonical URL for it.
_SEM_SAFE = "!*'()"


def encode_semantic_id(semantic_id: str) -> str:
    """One backend path segment; the backend decodes it exactly once."""
    return quote(semantic_id, safe=_SEM_SAFE)


def entity_url(entity_type: str, semantic_id: str) -> str:
    # The site route is a rest param: '/' stays a separator, the segments are encoded.
    return f"{SITE_URL}/{entity_type}/{quote(semantic_id, safe=_SEM_SAFE + '/')}"


def set_backend(url: str) -> None:
    """Retarget the backend at runtime (in-process callers, e.g. the verifier).

    The spawned MCP server process instead reads RANKLESS_BE_URL at import.
    """
    global BE_URL
    BE_URL = url
    from mcp_server import client

    client.reset()
