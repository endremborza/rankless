"""Shared identity and lifecycle for AI-agent runs.

Every agentic workflow — deep exploration and the object-store generators —
names its runs `<workflow>-<scope>-<UTC stamp>`, registers them as
`mcp_sessions` rows, and is spawnable by the host worker through the
`WORKFLOWS` registry. Adding a workflow means one registry entry plus a module
with its prompts (the generators share their whole engine, see object_mining.py);
the worker, the session pages, and the run naming need no new code. The
frontend mirrors the naming in `src/lib/mcp-util.ts` and the params/meta shapes
in `src/lib/types/mcp.ts`.

A row's `params.origin` records who started the run: rows queued from `/mcp`
have none (web), self-registered CLI runs carry `"origin": "cli"` so the
worker's orphan recovery never re-queues a run it does not own.
"""

import json
import re
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from protocli import Dispatcher

from pyscripts import paths

STAMP_FMT = "%Y%m%dT%H%M%S"
GENERATED_FMT = "%Y-%m-%dT%H:%M:%SZ"
DB_TIME_FMT = "%Y-%m-%d %H:%M:%S"
# Mirrors NAME_RE in src/lib/server/mcp-sessions.ts.
NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")

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


def import_run(con: sqlite3.Connection, src: Path, visibility: str) -> bool:
    """Register a finished deep run made elsewhere (`deep.py --no-store`, another
    box) as a done session: the dir is copied under the sessions root and its
    findings.json meta becomes the row. False when the name is already taken."""
    name = src.name
    if not NAME_RE.match(name):
        raise SystemExit(f"{name}: not a session name")
    meta = json.loads((src / "findings.json").read_text())["meta"]
    if meta["type"] != "deep":
        raise SystemExit(f"{name}: generator runs register on the box that mines them")
    con.executescript(SESSIONS_SCHEMA)
    if con.execute("SELECT 1 FROM mcp_sessions WHERE name = ?", (name,)).fetchone():
        return False
    dst = Path(paths.sessions_root()) / name
    if dst.exists():
        raise SystemExit(f"{dst} exists without a session row; remove it first")
    shutil.copytree(src, dst)
    params = _deep_params(meta)
    at = datetime.strptime(meta["generated"], GENERATED_FMT).strftime(DB_TIME_FMT)
    with con:
        con.execute(
            "INSERT INTO mcp_sessions (name, status, visibility, title, params, meta,"
            " created_at, updated_at) VALUES (?, 'done', ?, ?, ?, ?, ?, ?)",
            (
                name,
                visibility,
                deep_title(params),
                json.dumps(params),
                json.dumps(meta),
                at,
                at,
            ),
        )
    return True


def deep_title(params: dict) -> str:
    """Mirrors sessionTitle in src/lib/server/mcp-sessions.ts for deep params."""
    if params.get("investigate"):
        return f"Deepening {params['investigate']}"
    return (
        params.get("subject")
        or params.get("question")
        or f"{', '.join(params['foci'])} on {params['backend']}"
    )


def _deep_params(meta: dict) -> dict:
    """The queue params (`DeepParams` in src/lib/types/mcp.ts) a run's meta implies."""
    return {
        "type": "deep",
        "backend": meta["backendUrl"]
        if meta["backend"] == "custom"
        else meta["backend"],
        "foci": meta["foci"],
        "subject": meta["subject"],
        "question": meta["question"],
        "investigate": meta["investigate"],
        "model": meta["model"],
        "origin": "cli",
    }


def _import_cmd(*dirs: str, public: bool = False, db: str = "") -> None:
    """Register finished deep-run dirs (deep.py --no-store output) as done
    sessions under the sessions root; --public lists them on /mcp."""
    con = sqlite3.connect(db or paths.db_path())
    try:
        for d in dirs:
            src = Path(d)
            done = import_run(con, src, "public" if public else "private")
            print(f"{src.name}: {'registered' if done else 'already registered'}")
    finally:
        con.close()


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
    "rankless-game-card-mining": Workflow(
        _generation_argv("rankless-game-card-mining"), self_closing=True
    ),
    "impact-stories": Workflow(_generation_argv("impact-stories"), self_closing=True),
}

_dispatcher = Dispatcher("pyscripts runs", {"import": _import_cmd})
