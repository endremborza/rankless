"""Host worker for admin-created MCP agent runs.

Runs as a systemd `--user` service on the host. Polls the shared SQLite
(`mcp_sessions`) for `queued` rows, claims one atomically, and spawns the row's
workflow via the `pyscripts.explore.runs` registry (`params.type`; deep
exploration when absent). Deep runs write into the session's directory under
`$MCP_SESSIONS_ROOT` and the worker ingests the resulting `findings.json` meta;
self-closing workflows (the object-store generators) own their session row and
the worker only checks the exit code. One run at a time; robust across the
blue/green frontend workers because claiming is a single atomic UPDATE.

    uv run -m pyscripts.mcp_worker [--once]     # make mcp-worker

Env: RANKLESS_DB_PATH (default data/rankless.sqlite), MCP_SESSIONS_ROOT
(default data/mcp-sessions), MCP_WORKER_MODEL (default claude-sonnet-5),
MCP_WORKER_RUNNER (default claude-cli; see pyscripts/explore/runner.py),
MCP_WORKER_POLL_S (default 5). The claude-cli runner needs an authenticated
`claude` CLI on the host.
"""

import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

from pyscripts import paths
from pyscripts.explore.runs import SESSIONS_SCHEMA, WORKFLOWS

DB_PATH = paths.db_path()
SESSIONS_ROOT = paths.sessions_root()
DEFAULT_MODEL = os.environ.get("MCP_WORKER_MODEL", "claude-sonnet-5")
RUNNER = os.environ.get("MCP_WORKER_RUNNER", "claude-cli")
POLL_S = int(os.environ.get("MCP_WORKER_POLL_S", "5"))


def main() -> int:
    once = "--once" in sys.argv
    print(f"[mcp-worker] db={DB_PATH} root={SESSIONS_ROOT} model={DEFAULT_MODEL}")
    _recover_orphans()
    while True:
        conn = _connect()
        try:
            claimed = _claim_next(conn)
            if claimed:
                _process(conn, claimed["name"], json.loads(claimed["params"]))
        finally:
            conn.close()
        if once:
            break
        if not claimed:
            time.sleep(POLL_S)
    return 0


def _recover_orphans() -> None:
    """Re-queue worker-owned rows left 'running' by a killed worker (their
    processes die with it). Self-registered CLI runs (params.origin = 'cli')
    are not the worker's to restart."""
    conn = _connect()
    try:
        n = conn.execute(
            "UPDATE mcp_sessions SET status='queued', updated_at=datetime('now') "
            "WHERE status='running' "
            "AND COALESCE(json_extract(params, '$.origin'), '') != 'cli'"
        ).rowcount
        conn.commit()
        if n:
            print(f"[mcp-worker] re-queued {n} orphaned run(s)")
    finally:
        conn.close()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SESSIONS_SCHEMA)
    conn.row_factory = sqlite3.Row
    return conn


def _claim_next(conn: sqlite3.Connection) -> sqlite3.Row | None:
    row = conn.execute(
        "UPDATE mcp_sessions SET status='running', updated_at=datetime('now') "
        "WHERE name = (SELECT name FROM mcp_sessions WHERE status='queued' "
        "ORDER BY created_at LIMIT 1) RETURNING name, params"
    ).fetchone()
    conn.commit()
    return row


def _process(conn: sqlite3.Connection, name: str, params: dict) -> None:
    print(f"[mcp-worker] running {name}: {params}")
    wf_type = params.get("type", "deep")
    workflow = WORKFLOWS.get(wf_type)
    if workflow is None:
        _fail(conn, name, f"unknown workflow type {wf_type!r}")
        return
    argv = workflow.build_argv(name, params, DEFAULT_MODEL, RUNNER, SESSIONS_ROOT)
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, check=False)
    except OSError as exc:
        _fail(conn, name, f"spawn failed: {exc}")
        return
    if workflow.self_closing:
        if proc.returncode == 0:
            print(f"[mcp-worker] done {name}")
        else:
            _fail(
                conn, name, (proc.stderr or proc.stdout or f"{wf_type} failed")[-2000:]
            )
        return
    findings = Path(SESSIONS_ROOT) / name / "findings.json"
    if proc.returncode == 0 and findings.exists():
        meta = json.loads(findings.read_text()).get("meta", {})
        conn.execute(
            "UPDATE mcp_sessions SET status='done', meta=?, updated_at=datetime('now') "
            "WHERE name=?",
            (json.dumps(meta), name),
        )
        conn.commit()
        print(f"[mcp-worker] done {name}")
    else:
        tail = (proc.stderr or proc.stdout or "deep.py produced no findings.json")[
            -2000:
        ]
        _fail(conn, name, tail)


def _fail(conn: sqlite3.Connection, name: str, error: str) -> None:
    conn.execute(
        "UPDATE mcp_sessions SET status='failed', error=?, updated_at=datetime('now') "
        "WHERE name=?",
        (error, name),
    )
    conn.commit()
    print(f"[mcp-worker] FAILED {name}: {error[:200]}")


if __name__ == "__main__":
    raise SystemExit(main())
