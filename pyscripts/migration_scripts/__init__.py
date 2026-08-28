"""One-time scripts that bring already-deployed state up to what the code expects.

Nothing in this package is production code. The app, the pipeline and the ops
commands assume the current schema and the current on-disk formats: they never
inspect a database to see which version built it, and never carry a branch for
an older shape. When a change leaves a deployed database or data directory
behind, the catch-up lands here as a script, runs once per box, and is deleted
in the same breath — git keeps the history, the codebase does not.

Scripts are stdlib-only and idempotent, so they run on a serving box's
runtime-only venv and survive a second invocation:

    python3 -m pyscripts.migration_scripts.<name> [--db PATH]
"""

import sqlite3

from pyscripts import paths


def user_db(db: str | None = None) -> sqlite3.Connection:
    con = sqlite3.connect(db or paths.db_path())
    con.execute("PRAGMA busy_timeout = 30000")
    return con


def columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
