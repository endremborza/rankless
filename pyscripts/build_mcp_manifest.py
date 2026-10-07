"""Bake the MCP page manifest from the live Python sources.

Single source of truth: the tool docstrings, resources, and prompts are read
straight from `mcp_server` (a tool's REST endpoint from deep's curl map), so the
`/mcp` page never restates them. The texts built from served values (the table tools'
metric lists, the era's years) are filled from `--backend` the way the server fills them
at its start.

    uv run -m pyscripts.build_mcp_manifest [--backend alpha]   # make mcp-manifest ARGS=...
"""

import argparse
import inspect
import json
import os
from datetime import datetime
from pathlib import Path

import mcp_server
from mcp_server import BACKENDS, resolve_backend
from mcp_server.prompts import PROMPTS
from mcp_server.resources import resources
from mcp_server.server import PLAIN_TOOLS, fetch
from mcp_server.tools import TOOLS, describe
from pyscripts.explore import deep

OUT_PATH = Path("src/lib/assets/data/mcp-manifest.json")

# Public hosted MCP endpoint (streamable-http); override per deployment.
MCP_PUBLIC_URL = os.environ.get(
    "MCP_PUBLIC_URL", BACKENDS["alpha"].removesuffix("/v1") + "/mcp"
)
PUBLIC_BE_URL = os.environ.get("MCP_PUBLIC_BE_URL", BACKENDS["live"])


def main() -> int:
    p = argparse.ArgumentParser(description="Bake the MCP page manifest.")
    p.add_argument(
        "--backend",
        default="local",
        help=f"backend the served texts are read from: one of {list(BACKENDS)} or a "
        "/v1 base URL (default: %(default)s).",
    )
    mcp_server.set_backend(resolve_backend(p.parse_args().backend)[0])
    methodology = fetch("/methodology")
    describe(fetch("/columns"), methodology)
    manifest = {
        "generated": datetime.now().strftime("%Y-%m-%d"),
        "connect": _connect(),
        "tools": _tools(),
        "resources": [
            {"uri": uri, "text": text.strip()}
            for uri, text in resources(methodology).items()
        ],
        "prompts": _prompts(),
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"[mcp-manifest] {len(manifest['tools'])} tools -> {OUT_PATH}")
    return 0


def _connect() -> dict:
    proxy = json.dumps(
        {"mcpServers": {"rankless": {"type": "http", "url": MCP_PUBLIC_URL}}}, indent=2
    )
    return {
        "url": MCP_PUBLIC_URL,
        "transport": "streamable-http",
        "snippets": [
            {
                "label": "Claude Code",
                "cmd": f"claude mcp add --transport http rankless {MCP_PUBLIC_URL}",
            },
            {
                "label": "Claude.ai / Claude Desktop",
                "cmd": "Settings → Connectors → Add custom connector → "
                f"name: rankless, URL: {MCP_PUBLIC_URL}",
            },
            {"label": "MCP config (.mcp.json / Cursor / other clients)", "cmd": proxy},
            {
                "label": "Or run the stdio proxy against the public REST API",
                "cmd": f"RANKLESS_BE_URL={PUBLIC_BE_URL} uv run -m mcp_server",
            },
        ],
    }


def _tools() -> list[dict]:
    out = []
    for fn in (*TOOLS, *PLAIN_TOOLS):
        doc = inspect.getdoc(fn) or ""
        out.append(
            {
                "name": fn.__name__,
                "endpoint": _endpoint(fn.__name__),
                "summary": doc.split("\n", 1)[0],
                "description": doc,
            }
        )
    return out


def _endpoint(tool_name: str) -> str:
    entry = deep._CURL_MAP.get(tool_name)
    if entry:
        return "/v1" + entry[0]
    return {"get_citation_tree": "/v1/trees/{entity_type}/{semantic_id}"}.get(
        tool_name, ""
    )


def _prompts() -> list[dict]:
    return [
        {"name": fn.__name__, "description": inspect.getdoc(fn) or ""} for fn in PROMPTS
    ]


if __name__ == "__main__":
    raise SystemExit(main())
