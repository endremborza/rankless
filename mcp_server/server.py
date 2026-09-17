"""FastMCP wiring: registers tools, resources and prompts.

Default transport is stdio (local proxy for Claude Code / Desktop). For the
hosted public endpoint, run with `--transport streamable-http` behind nginx and
set MCP_PUBLIC_HOSTS to the Host header values the proxy forwards; without it
the SDK's guard admits localhost only.
"""

import argparse
import os
import sys
import time

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

import mcp_server
from mcp_server.grounding import GROUNDING_TOOLS
from mcp_server.prompts import PROMPTS
from mcp_server.receipts import with_receipt
from mcp_server.resources import AGENT_GUIDE, RESOURCES
from mcp_server.tools import TOOLS, describe

LOCAL_HOSTS = ["127.0.0.1:*", "localhost:*"]
REGISTRY_ATTEMPTS = 3
REGISTRY_RETRY_S = 5


def transport_security(public_hosts: str) -> TransportSecuritySettings | None:
    """Host-header guard admitting the public hosts plus localhost; None keeps
    the SDK's localhost-only default."""
    hosts = [h.strip() for h in public_hosts.split(",") if h.strip()]
    if not hosts:
        return None
    return TransportSecuritySettings(
        allowed_hosts=[*hosts, *LOCAL_HOSTS],
        allowed_origins=[f"https://{h}" for h in hosts]
        + [f"http://{h}" for h in LOCAL_HOSTS],
    )


def fetch_registry() -> dict:
    """The backend's metric registry, the source of the table tools' descriptions.
    An unreachable backend is a failed start: the box unit restarts on failure."""
    url = f"{mcp_server.BE_URL}/columns"
    for attempt in range(1, REGISTRY_ATTEMPTS + 1):
        try:
            resp = httpx.get(url, timeout=10.0)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            if attempt == REGISTRY_ATTEMPTS:
                raise SystemExit(f"metric registry unreachable at {url}: {exc}")
            print(f"metric registry not up yet ({exc}); retrying", file=sys.stderr)
            time.sleep(REGISTRY_RETRY_S)
    raise AssertionError("unreachable")


def build(registry: dict) -> FastMCP:
    """The server with every tool, prompt and resource registered; the table tools
    describe themselves from the registry."""
    describe(registry)
    mcp = FastMCP(
        "rankless",
        instructions=AGENT_GUIDE,
        transport_security=transport_security(os.environ.get("MCP_PUBLIC_HOSTS", "")),
    )
    for fn in TOOLS:
        mcp.tool()(with_receipt(fn))
    for fn in GROUNDING_TOOLS:
        mcp.tool()(fn)
    for prompt_fn in PROMPTS:
        mcp.prompt()(prompt_fn)
    for uri, text in RESOURCES.items():
        _register_resource(mcp, uri, text)
    return mcp


def _register_resource(mcp: FastMCP, uri: str, text: str) -> None:
    @mcp.resource(uri)
    def _res() -> str:
        return text


def main() -> None:
    p = argparse.ArgumentParser(description="Rankless MCP server.")
    p.add_argument(
        "--transport",
        default=os.environ.get("MCP_TRANSPORT", "stdio"),
        choices=["stdio", "sse", "streamable-http"],
    )
    p.add_argument("--host", default=os.environ.get("MCP_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("MCP_PORT", "8000")))
    args = p.parse_args()
    mcp = build(fetch_registry())
    if args.transport != "stdio":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
    mcp.run(transport=args.transport)
