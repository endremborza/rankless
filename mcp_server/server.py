"""FastMCP wiring: registers tools, resources and prompts; stdio transport."""

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
    mcp.run()
