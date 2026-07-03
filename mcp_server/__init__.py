"""MCP proxy exposing the rankless backend to any MCP client.

Phase 1 of the MCP surface (.cril/ideas.md §8): a thin Python process that
proxies tool calls to the low-latency Rust backend, shapes responses for
agents (flatten trees, truncate, attach rankless.org backlinks), and keeps
rate/agent logic out of the data hot path.

Run over stdio with `uv run -m mcp_server`.
"""

import os

BE_URL = os.environ.get("RANKLESS_BE_URL", "http://127.0.0.1:3038/v1")
SITE_URL = os.environ.get("RANKLESS_SITE_URL", "https://rankless.org")

ROOT_TYPES = ("authors", "institutions", "sources", "countries", "subfields")
SEARCH_TYPES = (*ROOT_TYPES, "all")


def entity_url(entity_type: str, semantic_id: str) -> str:
    return f"{SITE_URL}/{entity_type}/{semantic_id}"


def set_backend(url: str) -> None:
    """Retarget the backend at runtime (in-process callers, e.g. the verifier).

    The spawned MCP server process instead reads RANKLESS_BE_URL at import.
    """
    global BE_URL
    BE_URL = url
    from mcp_server import client

    client.reset()
