"""Move curated MCP + ledger data between a local checkout and a deployed box.

Transfers `mcp_sessions`, `ledger_events`, `ledger_runs`, `owner_pins` between two
copies of `data/rankless.sqlite` — never the auth `sessions` table. Runs on the
receiving side against a shipped copy of the source DB; `pyscripts.deploy` moves
the `data/mcp-sessions/` artifact dirs alongside it.

    python -m pyscripts.mcp_db <target_db> <incoming_db> merge|mirror

- merge:  union rows; the source never clobbers the target (INSERT OR IGNORE).
          Auto-id rows (`ledger_events`) drop their id so the target assigns a
          fresh one and dedup falls to the logical unique index, not the id.
- mirror: replace the target's copy of each table with the source's, verbatim.

Stdlib only — it also runs on the serving box's runtime-only venv.
"""

import sqlite3
import sys

TABLES = ("mcp_sessions", "ledger_events", "ledger_runs", "owner_pins")


def transfer(target_db: str, incoming_db: str, mode: str) -> None:
    if mode not in ("merge", "mirror"):
        raise SystemExit(f"mode must be merge|mirror, got {mode!r}")
    con = sqlite3.connect(target_db)
    con.execute("PRAGMA busy_timeout = 30000")
    con.execute("ATTACH DATABASE ? AS src", (incoming_db,))
    try:
        with con:
            for table in TABLES:
                _transfer_table(con, table, mode)
    finally:
        con.execute("DETACH DATABASE src")
        con.close()


def _transfer_table(con: sqlite3.Connection, table: str, mode: str) -> None:
    if not _has_table(con, "src", table):
        return
    _ensure_target_table(con, table)
    if mode == "mirror":
        con.execute(f"DELETE FROM main.{table}")
        cols = _columns(con, table)  # verbatim copy, ids included
        verb = "INSERT"
    else:
        skip = _autoinc_pks(con, table)
        cols = [c for c in _columns(con, table) if c not in skip]
        verb = "INSERT OR IGNORE"
    collist = ", ".join(cols)
    con.execute(
        f"{verb} INTO main.{table} ({collist}) SELECT {collist} FROM src.{table}"
    )


def _has_table(con: sqlite3.Connection, schema: str, table: str) -> bool:
    row = con.execute(
        f"SELECT 1 FROM {schema}.sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _ensure_target_table(con: sqlite3.Connection, table: str) -> None:
    if _has_table(con, "main", table):
        return
    ddl = con.execute(
        "SELECT sql FROM src.sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    con.execute(ddl[0])


def _columns(con: sqlite3.Connection, table: str) -> list[str]:
    return [r[1] for r in con.execute(f"PRAGMA main.table_info({table})")]


def _autoinc_pks(con: sqlite3.Connection, table: str) -> set[str]:
    # INTEGER PRIMARY KEY columns are rowid aliases: merge lets the target assign
    # fresh ids so independently-numbered rows from each box never collide.
    return {
        r[1]
        for r in con.execute(f"PRAGMA main.table_info({table})")
        if r[5] and r[2].upper() == "INTEGER"
    }


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: python -m pyscripts.mcp_db <target> <incoming> merge|mirror"
        )
    transfer(sys.argv[1], sys.argv[2], sys.argv[3])


if __name__ == "__main__":
    main()
