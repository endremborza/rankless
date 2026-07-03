"""Bake the MCP demo-page manifest from the live Python sources.

Single source of truth: the tool docstrings, focus blocks, argparse help,
resources, and prompts are read straight from `mcp_server` / `pyscripts.explore`,
so the `/mcp` page never restates them. A trimmed, sanitized slice of one real
exploration writeup is folded in as the showcase (writeups themselves live in the
gitignored .cril/, so a committed sample is the only way to ship one).

    uv run -m pyscripts.build_mcp_manifest [--showcase <run-dir>]   # make mcp-manifest
"""

import argparse
import inspect
import json
import os
from datetime import datetime
from pathlib import Path

from mcp_server.prompts import PROMPTS
from mcp_server.resources import RESOURCES
from mcp_server.tools import TOOLS
from pyscripts.explore import deep

OUT_PATH = Path("src/lib/assets/data/mcp-manifest.json")
DEFAULT_SHOWCASE = deep.WRITEUPS_DIR / "subject-lengyel"
SHOWCASE_FOCI = 3  # keep the page compact
OPTION_FLAGS = ("--backend", "--foci", "--subject", "--question", "--investigate")

# Public hosted MCP endpoint (streamable-http); override per deployment.
MCP_PUBLIC_URL = os.environ.get("MCP_PUBLIC_URL", "https://alpha-api.rankless.org/mcp")
PUBLIC_BE_URL = os.environ.get("MCP_PUBLIC_BE_URL", "https://alpha-api.rankless.org/v1")

COMMANDS = [
    ("Story mining (live)", "make deep-explore ARGS='--backend live --foci share'"),
    (
        "A specific subject",
        "make deep-explore ARGS='--backend live --subject \"Hungary\"'",
    ),
    ("Deepen a past finding", "make deep-explore ARGS='--investigate live-demo:f5'"),
    ("Run the MCP server", "make mcp-server"),
]


def main() -> int:
    ap = argparse.ArgumentParser(description="Bake the MCP demo-page manifest.")
    ap.add_argument(
        "--showcase", default=str(DEFAULT_SHOWCASE), help="writeup run dir."
    )
    args = ap.parse_args()

    manifest = {
        "generated": datetime.now().strftime("%Y-%m-%d"),
        "connect": _connect(),
        "tools": _tools(),
        "foci": _foci(),
        "options": _options(),
        "resources": [
            {"uri": uri, "text": text.strip()} for uri, text in RESOURCES.items()
        ],
        "prompts": _prompts(),
        "commands": [{"label": label, "cmd": cmd} for label, cmd in COMMANDS],
        "showcase": _showcase(Path(args.showcase)),
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    n = len(manifest["tools"])
    show = "with" if manifest["showcase"] else "no"
    print(f"[mcp-manifest] {n} tools, {show} showcase -> {OUT_PATH}")
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
            {"label": "MCP config (.mcp.json / Cursor / Desktop)", "cmd": proxy},
            {
                "label": "Or run the stdio proxy against the public REST API",
                "cmd": f"RANKLESS_BE_URL={PUBLIC_BE_URL} uv run -m mcp_server",
            },
        ],
    }


def _tools() -> list[dict]:
    out = []
    for fn in TOOLS:
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


def _foci() -> list[dict]:
    out = []
    for name, block in deep._FOCUS_BLOCKS.items():
        # Strip the leading `FOCUS "x" - ` prompt framing; keep the description.
        text = block.replace("{question}", "").split(" - ", 1)[-1].replace("\n", " ")
        out.append({"name": name, "description": " ".join(text.split())})
    return out


def _options() -> list[dict]:
    by_flag = {
        a.option_strings[0]: a for a in deep.build_parser()._actions if a.option_strings
    }
    return [
        {"flag": flag, "help": by_flag[flag].help}
        for flag in OPTION_FLAGS
        if flag in by_flag
    ]


def _prompts() -> list[dict]:
    return [
        {"name": fn.__name__, "description": inspect.getdoc(fn) or ""} for fn in PROMPTS
    ]


def _showcase(run_dir: Path) -> dict | None:
    path = run_dir / "findings.json"
    if not path.exists():
        print(f"[mcp-manifest] no showcase at {path}; skipping.")
        return None
    data = json.loads(path.read_text())
    meta = data.get("meta", {})
    findings = [f for f in data.get("findings", []) if f.get("_verified")][
        :SHOWCASE_FOCI
    ]
    return {
        "subject": meta.get("subject"),
        "backend": meta.get("backend"),
        "model": meta.get("model"),
        "counts": meta.get("counts"),
        "runtimeSeconds": meta.get("runtimeSeconds"),
        "findings": [_trim_finding(f) for f in findings],
        "endpointSuggestions": data.get("endpointSuggestions", [])[:2],
    }


def _trim_finding(f: dict) -> dict:
    return {
        "id": f.get("id"),
        "title": f.get("title"),
        "focus": f.get("focus"),
        "shareKind": f.get("share_kind"),
        "description": f.get("description"),
        "entities": f.get("entities", []),
        "numbers": [
            {
                "label": m.get("label"),
                "value": m.get("reproduced"),
                "tool": m.get("tool"),
                "path": m.get("path"),
            }
            for m in f.get("metrics", [])
            if not m.get("error")
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
