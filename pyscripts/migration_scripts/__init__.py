"""One-time scripts that bring already-deployed state up to what the code expects.

Nothing in this package is production code, and the package is EMPTY in its
steady state. The app, the pipeline and the ops commands assume the current
schema and the current on-disk formats: they never inspect a database to see
which version built it, and never carry a branch for an older shape. When a
change leaves a deployed database or data directory behind, the catch-up lands
here as a script for one deploy cycle: every code deploy (`deploy.Transper
.update_fe`) runs whatever is here on the box before the new code serves, the
change's author runs it once on the primary host's own DB, and the script is
deleted in the next commit — ship/promote refuse while any remain
(`deploy._assert_release_tree`), so a script never outlives one release. Git
keeps the history, the codebase does not.

Scripts are stdlib-only and idempotent, so they run on a serving box's
runtime-only venv and survive a second invocation:

    python3 -m pyscripts.migration_scripts.<name> [--db PATH]
"""

import sqlite3
from pathlib import Path

from pyscripts import paths


def module_names() -> list[str]:
    """Every script in the package, in run order — a deploy runs them all, each
    one a no-op once applied; the release gate requires this to be empty."""
    return sorted(p.stem for p in Path(__file__).parent.glob("[a-z]*.py"))


def user_db(db: str | None = None) -> sqlite3.Connection:
    con = sqlite3.connect(db or paths.db_path())
    con.execute("PRAGMA busy_timeout = 30000")
    return con


def columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
