"""FastMCP wiring: registers tools, resources and prompts.

Default transport is stdio (local proxy for Claude Code / Desktop). For the
hosted public endpoint, run with `--transport streamable-http` behind nginx.
"""

import argparse
import os

from mcp.server.fastmcp import FastMCP

from mcp_server.prompts import PROMPTS
from mcp_server.resources import RESOURCES
from mcp_server.tools import TOOLS

mcp = FastMCP("rankless")

for fn in TOOLS:
    mcp.tool()(fn)

for prompt_fn in PROMPTS:
    mcp.prompt()(prompt_fn)


def _register_resource(uri: str, text: str) -> None:
    @mcp.resource(uri)
    def _res() -> str:
        return text


for _uri, _text in RESOURCES.items():
    _register_resource(_uri, _text)


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
    if args.transport != "stdio":
        mcp.settings.host = args.host
        mcp.settings.port = args.port
    mcp.run(transport=args.transport)
