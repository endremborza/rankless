"""Move the user DB (MCP + ledger + auth) between a local checkout and a deployed box.

Transfers every curated table of `data/rankless.sqlite` between two copies of it:
`mcp_sessions`, `ledger_events`, `ledger_runs`, `owner_pins`, `users`,
`email_consents`, the review tables `subject_enrichment` / `review_verdicts`
(keyed by external ids / subject hashes, so rows stay valid across boxes), and
auth `sessions` (year-long TTL: dropping them logs everyone out on each deploy),
of which only unexpired rows move. Runs on the receiving side against a shipped
copy of the source DB; `pyscripts.deploy` moves the `data/mcp-sessions/` artifact
dirs alongside it.

    python -m pyscripts.mcp_db <target_db> <incoming_db> merge|mirror
    python -m pyscripts.mcp_db snapshot <src_db> <dst>

- merge:    union rows; the source never clobbers the target (INSERT OR IGNORE,
            plus a NULL-safe exact-row guard so tables without a unique index,
            e.g. `email_consents`, stay duplicate-free on re-merge). Auto-id
            rows (`ledger_events`) drop their id so the target assigns a fresh
            one and dedup falls to the logical unique index, not the id.
            `ledger_events.moderation` is additionally reconciled by logical key
            `(orcid, kind, subject_hash)`: an incoming decision flips a target
            row still `pending_review`; a decided target never reverts, and two
            conflicting decisions keep the target's (with a warning).
- mirror:   replace the target's copy of each table with the source's, verbatim.
- snapshot: consistent hot copy of a live DB (see `snapshot` below) — the shape
            in which a DB is moved between boxes, never the file rsync'd raw.

Stdlib only — it also runs on the serving box's runtime-only venv.
"""

import sqlite3
import sys

TABLES = (
    "mcp_sessions",
    "ledger_events",
    "ledger_runs",
    "owner_pins",
    "users",
    "email_consents",
    "subject_enrichment",
    "review_verdicts",
    "sessions",
)
ROW_FILTERS = {"sessions": "expires_at > datetime('now')"}
DECIDED_MODERATIONS = ("accepted", "rejected", "auto_ok")


def snapshot(src_db: str, dst: str) -> None:
    """Consistent copy of `src_db` at `dst` via SQLite's online backup API.

    Safe while a writer holds `src_db` open: reads a single consistent point and
    folds any WAL into `dst`, so `dst` is a standalone, fully-checkpointed file.
    Copying the live `.sqlite` with rsync would instead miss un-checkpointed
    commits in the `-wal` sidecar and risk a torn, malformed image.
    """
    src = sqlite3.connect(src_db)
    dst_con = sqlite3.connect(dst)
    try:
        with dst_con:
            src.backup(dst_con)
    finally:
        dst_con.close()
        src.close()


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
            if mode == "merge":
                _reconcile_moderation(con)
    finally:
        con.execute("DETACH DATABASE src")
        con.close()


def _transfer_table(con: sqlite3.Connection, table: str, mode: str) -> None:
    if not _has_table(con, "src", table):
        return
    _ensure_target_table(con, table)
    conds = [ROW_FILTERS[table]] if table in ROW_FILTERS else []
    if mode == "mirror":
        con.execute(f"DELETE FROM main.{table}")
        cols = _columns(con, table)  # verbatim copy, ids included
        verb = "INSERT"
    else:
        skip = _autoinc_pks(con, table)
        cols = [c for c in _columns(con, table) if c not in skip]
        verb = "INSERT OR IGNORE"
        # NULL-safe exact-row guard: keeps re-merges idempotent even for tables
        # with no logical unique index (OR IGNORE alone would duplicate them).
        match = " AND ".join(f"main.{table}.{c} IS src.{table}.{c}" for c in cols)
        conds.append(f"NOT EXISTS (SELECT 1 FROM main.{table} WHERE {match})")
    collist = ", ".join(cols)
    where = f" WHERE {' AND '.join(conds)}" if conds else ""
    con.execute(
        f"{verb} INTO main.{table} ({collist}) SELECT {collist} FROM src.{table}{where}"
    )


def _reconcile_moderation(con: sqlite3.Connection) -> None:
    # INSERT OR IGNORE never touches a ledger_events row both boxes already hold,
    # so a decision made on the source box would leave the target's copy pending
    # forever; copy the decision over by the merge-stable logical key.
    if not (
        _has_table(con, "src", "ledger_events")
        and _has_table(con, "main", "ledger_events")
    ):
        return
    decided = ", ".join(f"'{m}'" for m in DECIDED_MODERATIONS)
    key_match = (
        "s.orcid = main.ledger_events.orcid"
        " AND s.kind = main.ledger_events.kind"
        " AND s.subject_hash = main.ledger_events.subject_hash"
        " AND s.revoked_at IS NULL"
    )
    conflicts = con.execute(
        f"SELECT t.orcid, t.kind, t.subject_hash, t.moderation, s.moderation"
        f" FROM main.ledger_events t JOIN src.ledger_events s"
        f" ON s.orcid = t.orcid AND s.kind = t.kind AND s.subject_hash = t.subject_hash"
        f" WHERE t.revoked_at IS NULL AND s.revoked_at IS NULL"
        f" AND t.moderation IN ({decided}) AND s.moderation IN ({decided})"
        f" AND t.moderation != s.moderation"
    ).fetchall()
    for orcid, kind, shash, kept, ignored in conflicts:
        print(
            f"warning: moderation conflict on {orcid}|{kind}|{shash}:"
            f" keeping {kept!r}, ignoring incoming {ignored!r}",
            file=sys.stderr,
        )
    con.execute(
        f"UPDATE main.ledger_events"
        f" SET (moderation, moderated_by, moderated_at) ="
        f" (SELECT s.moderation, s.moderated_by, s.moderated_at"
        f"  FROM src.ledger_events s WHERE {key_match} AND s.moderation IN ({decided}))"
        f" WHERE moderation = 'pending_review' AND revoked_at IS NULL"
        f" AND EXISTS (SELECT 1 FROM src.ledger_events s"
        f"  WHERE {key_match} AND s.moderation IN ({decided}))"
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
    args = sys.argv[1:]
    if len(args) == 3 and args[0] == "snapshot":
        snapshot(args[1], args[2])
    elif len(args) == 3:
        transfer(args[0], args[1], args[2])
    else:
        raise SystemExit(
            "usage: python -m pyscripts.mcp_db <target> <incoming> merge|mirror\n"
            "       python -m pyscripts.mcp_db snapshot <src> <dst>"
        )


if __name__ == "__main__":
    main()
