"""MCP proxy exposing the rankless backend to any MCP client.

A thin Python process that
proxies tool calls to the low-latency Rust backend, shapes responses for
agents (flatten trees, truncate, attach rankless.org backlinks), and keeps
rate/agent logic out of the data hot path.

Run over stdio with `uv run -m mcp_server`.
"""

import os
from urllib.parse import quote, urlencode

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


SITE_VAR = "RANKLESS_SITE_URL"
RENDER_VAR = "RANKLESS_RENDER_URL"
SITE_URL = os.environ.get(SITE_VAR, "https://rankless.org")
# Where a card URL is fetched to render it: the site, or a frontend serving the same
# cards from elsewhere (a local dev server over a tunnel) while the site does not.
RENDER_URL = os.environ.get(RENDER_VAR, SITE_URL)

ROOT_TYPES = ("authors", "institutions", "sources", "countries", "subfields")
SEARCH_TYPES = (*ROOT_TYPES, "all")
VIEW_TYPES = (*ROOT_TYPES, "hit-papers")
# A laureate's prize code is its category's position here, counted from 1.
NOBEL_CATEGORIES = ("Physics", "Chemistry", "Physiology or Medicine", "Economics")


# JS encodeURIComponent's unreserved set, so an id encodes to the same bytes here
# as in the frontend and both produce the site's canonical URL for it.
_SEM_SAFE = "!*'()"


def encode_semantic_id(semantic_id: str) -> str:
    """One backend path segment; the backend decodes it exactly once."""
    return quote(semantic_id, safe=_SEM_SAFE)


def _sem_path(entity_type: str, semantic_id: str) -> str:
    # The site route is a rest param: '/' stays a separator, the segments are encoded.
    return f"{entity_type}/{quote(semantic_id, safe=_SEM_SAFE + '/')}"


def _with_query(url: str, query: dict | None) -> str:
    clean = {k: v for k, v in (query or {}).items() if v is not None}
    return f"{url}?{urlencode(clean)}" if clean else url


def entity_url(entity_type: str, semantic_id: str, query: dict | None = None) -> str:
    """The entity's page; `query` is the page's view state (`tree`, `since`)."""
    return _with_query(f"{SITE_URL}/{_sem_path(entity_type, semantic_id)}", query)


def card_url(
    kind: str, entity_type: str, semantic_id: str = "", query: dict | None = None
) -> str:
    """The share card `kind` of an entity, or of a type's cohort when `semantic_id`
    is empty, with the variant `query` (the parameters `make_card` lists)."""
    path = _sem_path(entity_type, semantic_id) if semantic_id else entity_type
    return _with_query(f"{SITE_URL}/card/{path}/{kind}.png", query)


def render_url(url: str) -> str:
    """`url` on the host that renders the cards."""
    if RENDER_URL != SITE_URL and url.startswith(SITE_URL):
        return RENDER_URL + url[len(SITE_URL) :]
    return url


def table_url(entity_type: str, query: dict) -> str:
    """The browse table showing one `/slice` query: the table page reads the same keys
    the backend takes, so the query is re-encoded as sent, never translated."""
    return _with_query(f"{SITE_URL}/{entity_type}/table", query)


def set_backend(url: str) -> None:
    """Retarget the backend at runtime (in-process callers, e.g. the verifier).

    The spawned MCP server process instead reads RANKLESS_BE_URL at import.
    """
    global BE_URL
    BE_URL = url
    from mcp_server import client

    client.reset()
