"""Shared identity and lifecycle for AI-agent runs.

Every agentic workflow — deep exploration and the object-store generators —
names its runs `<workflow>-<scope>-<UTC stamp>`, registers them as
`mcp_sessions` rows, and is spawnable by the host worker through the
`WORKFLOWS` registry. Adding a workflow means one registry entry plus a module
with its prompts (the generators share their whole engine, see generation.py);
the worker, the session pages, and the run naming need no new code. The
frontend mirrors the naming in `src/lib/mcp-util.ts` and the params/meta shapes
in `src/lib/types/mcp.ts`.

A row's `params.origin` records who started the run: rows queued from `/mcp`
have none (web), self-registered CLI runs carry `"origin": "cli"` so the
worker's orphan recovery never re-queues a run it does not own.
"""

import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable

STAMP_FMT = "%Y%m%dT%H%M%S"

SESSIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS mcp_sessions (
    name TEXT PRIMARY KEY, orcid TEXT, status TEXT NOT NULL DEFAULT 'queued',
    visibility TEXT NOT NULL DEFAULT 'private', title TEXT, params TEXT NOT NULL,
    meta TEXT, error TEXT, created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

ArgvBuilder = Callable[[str, dict, str, str, str], list[str]]


@dataclass(frozen=True)
class Workflow:
    # (name, params, default_model, runner, sessions_root) -> spawn argv
    build_argv: ArgvBuilder
    # True when the spawned process owns its session row (closes it with
    # done/failed + meta itself); the worker then only checks the exit code.
    self_closing: bool


def run_stamp() -> str:
    return datetime.now(UTC).strftime(STAMP_FMT)


def utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_name(workflow: str, scope: str) -> str:
    return f"{workflow}-{scope}-{run_stamp()}"


def open_run(con: sqlite3.Connection, name: str, title: str, params: dict) -> None:
    """Register a self-owned running session row; a no-op when the worker
    queued (and claimed) the row already."""
    con.executescript(SESSIONS_SCHEMA)
    with con:
        con.execute(
            "INSERT OR IGNORE INTO mcp_sessions (name, status, visibility, title,"
            " params) VALUES (?, 'running', 'private', ?, ?)",
            (name, title, json.dumps({**params, "origin": "cli"})),
        )


def close_run(
    con: sqlite3.Connection,
    name: str,
    status: str,
    meta: dict | None = None,
    error: str | None = None,
) -> None:
    with con:
        con.execute(
            "UPDATE mcp_sessions SET status = ?, meta = ?, error = ?,"
            " updated_at = datetime('now') WHERE name = ?",
            (status, json.dumps(meta) if meta else None, error, name),
        )


def _generation_argv(command: str) -> ArgvBuilder:
    def build(
        name: str, params: dict, model: str, runner: str, _root: str
    ) -> list[str]:
        return [
            sys.executable,
            "-m",
            "pyscripts",
            command,
            "--session",
            name,
            "--backend",
            params.get("backend", "live"),
            "--etype",
            params.get("etype", "institutions"),
            "--count",
            str(params.get("count", 24)),
            "--model",
            params.get("model") or model,
            "--engine",
            runner,
        ]

    return build


def _deep_argv(
    name: str, params: dict, model: str, runner: str, sessions_root: str
) -> list[str]:
    argv = [
        sys.executable,
        "-m",
        "pyscripts.explore.deep",
        "--out-root",
        sessions_root,
        "--out",
        name,
        "--backend",
        params.get("backend", "live"),
        "--model",
        params.get("model") or model,
        "--runner",
        runner,
    ]
    if foci := params.get("foci"):
        argv += ["--foci", ",".join(foci)]
    if params.get("subject"):
        argv += ["--subject", params["subject"]]
    if params.get("question"):
        argv += ["--question", params["question"]]
    if params.get("investigate"):
        argv += ["--investigate", params["investigate"]]
    if params.get("suggestEndpoints") is False:
        argv += ["--no-suggest-endpoints"]
    return argv


WORKFLOWS: dict[str, Workflow] = {
    "deep": Workflow(_deep_argv, self_closing=False),
    "game-cards": Workflow(_generation_argv("game-cards"), self_closing=True),
    "impact-stories": Workflow(_generation_argv("impact-stories"), self_closing=True),
}
