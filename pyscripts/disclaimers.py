"""Disclaimers on profile pages: a data note at the bottom of a profile's first card,
shown while the data run it was written against is served.

    uv run -m pyscripts disclaimers add --root-type authors --semantic-id <slug> --text "..."
    uv run -m pyscripts disclaimers remove --root-type authors --semantic-id <slug>
    uv run -m pyscripts disclaimers list

Run on the box whose site should show the note: the row goes into that box's user DB
with the run id of `APPLIED_MANIFEST` under `$OA_ROOT`, the file the site
compares it with (src/lib/server/disclaimers.ts). A new data run retires every earlier
note; its row stays until replaced or removed. `add` asks the box's backend for the
profile, so a mistyped slug fails here instead of never showing.
"""

import json
import os
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
from protocli import Dispatcher

from mcp_server import BE_URL, VIEW_TYPES, encode_semantic_id
from pyscripts import paths
from wire.rankless_rs.user_ledger import APPLIED_MANIFEST

load_dotenv()

# Mirrored in src/lib/server/db.ts, the reader.
SCHEMA = """
CREATE TABLE IF NOT EXISTS profile_disclaimers (
    root_type TEXT NOT NULL,
    semantic_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (root_type, semantic_id)
);
"""


def connect(db_path: str = "") -> sqlite3.Connection:
    con = sqlite3.connect(db_path or paths.db_path())
    con.execute("PRAGMA busy_timeout = 5000")
    con.executescript(SCHEMA)
    return con


def served_run_id() -> str:
    """The run id of the data this box serves, read where the site reads it."""
    manifest = Path(os.environ["OA_ROOT"]) / paths.USER_LEDGER_DIR / APPLIED_MANIFEST
    return json.loads(manifest.read_text())["run_id"]


def profile_name(root_type: str, semantic_id: str) -> str:
    url = f"{BE_URL}/views/{root_type}/{encode_semantic_id(semantic_id)}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            view = json.load(resp)
    except (urllib.error.URLError, ValueError) as exc:
        raise SystemExit(f"cannot ask {BE_URL} for {root_type}/{semantic_id}: {exc}")
    if not view or "name" not in view:
        raise SystemExit(f"no {root_type} profile {semantic_id!r} at {BE_URL}")
    return view["name"]


def add(*, root_type: str, semantic_id: str, text: str, db: str = "") -> None:
    """Put --text on the profile's page, replacing its current note; it shows while
    the run this box serves is served."""
    if root_type not in VIEW_TYPES:
        raise SystemExit(f"--root-type must be one of {', '.join(VIEW_TYPES)}")
    if not text.strip():
        raise SystemExit("--text is empty")
    name, run_id = profile_name(root_type, semantic_id), served_run_id()
    con = connect(db)
    try:
        with con:
            con.execute(
                "INSERT OR REPLACE INTO profile_disclaimers"
                " (root_type, semantic_id, run_id, text) VALUES (?, ?, ?, ?)",
                (root_type, semantic_id, run_id, text.strip()),
            )
    finally:
        con.close()
    print(f"{name} ({root_type}/{semantic_id}): shown while run {run_id} is served")


def remove(*, root_type: str, semantic_id: str, db: str = "") -> None:
    """Take the note off the profile's page."""
    con = connect(db)
    try:
        with con:
            gone = con.execute(
                "DELETE FROM profile_disclaimers WHERE root_type = ? AND semantic_id = ?",
                (root_type, semantic_id),
            ).rowcount
    finally:
        con.close()
    if not gone:
        raise SystemExit(f"no disclaimer on {root_type}/{semantic_id}")
    print(f"{root_type}/{semantic_id}: removed")


def rows(db: str = "") -> list[tuple[str, str, str, str]]:
    con = connect(db)
    try:
        return con.execute(
            "SELECT root_type, semantic_id, run_id, text FROM profile_disclaimers"
            " ORDER BY root_type, semantic_id"
        ).fetchall()
    finally:
        con.close()


def _list_cmd(*, db: str = "") -> None:
    """Every stored note, marked `shown` (written against the run this box serves)
    or `lapsed`."""
    served = served_run_id()
    for root_type, semantic_id, run_id, text in rows(db):
        state = "shown " if run_id == served else "lapsed"
        print(f"{state} {root_type}/{semantic_id} [{run_id}] {text}")


_dispatcher = Dispatcher(
    "pyscripts disclaimers",
    {"add": add, "remove": remove, "list": _list_cmd},
)
