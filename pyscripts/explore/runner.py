"""Pluggable mining engines: one call = one agentic session over the MCP tools.

The Claude Code CLI is the only engine today; the registry keeps deep.py and
the session worker engine-agnostic, so an SDK/API-based runner can slot in
without touching the mining or reproduction logic.
"""

import json
import sys
from dataclasses import dataclass
from typing import Callable

from pyscripts.explore import cli

DEFAULT_RUNNER = "claude-cli"
ALLOWED_TOOLS = "mcp__rankless"


@dataclass
class MineJob:
    system: str
    user: str
    model: str
    backend_url: str
    max_turns: int
    timeout_s: int


def run_claude_cli(job: MineJob) -> str:
    return cli.query_claude_cli(
        job.system,
        job.user,
        job.model,
        allowed_tools=ALLOWED_TOOLS,
        mcp_config=_mcp_config(job.backend_url),
        max_turns=job.max_turns,
        timeout_s=job.timeout_s,
    )


RUNNERS: dict[str, Callable[[MineJob], str]] = {"claude-cli": run_claude_cli}


def get_runner(name: str) -> Callable[[MineJob], str]:
    if name not in RUNNERS:
        raise SystemExit(f"unknown runner {name!r}; choose from {list(RUNNERS)}")
    return RUNNERS[name]


def _mcp_config(backend_url: str) -> str:
    # sys.executable, not `uv run`: MCP clients give up on slow spawns.
    return json.dumps(
        {
            "mcpServers": {
                "rankless": {
                    "command": sys.executable,
                    "args": ["-m", "mcp_server"],
                    "env": {"RANKLESS_BE_URL": backend_url},
                }
            }
        }
    )
