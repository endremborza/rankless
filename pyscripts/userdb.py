"""One home for the user-data unit: `data/rankless.sqlite` plus the artifact
dirs it references (`data/mcp-sessions/` run outputs, `data/mcp-objects/`
object-store bundles). Everything that moves or preserves that unit lives
here: consistent snapshots, cross-box table transfer with decision
reconciliation, and retained off-box backups. `pyscripts.deploy` provides the
ssh/rsync transport and calls in; flows in docs/mcp-server.md + docs/deploy.md.

Transfers cover every curated table: `mcp_sessions`, `mcp_objects` (payload-free
object index; review statuses reconcile by version key), `game_results` +
`game_daily` (play logs, daily-card pins), `ledger_events` (+ moderation
reconciliation), `ledger_runs`, `owner_pins`, `users`, `email_consents`,
`subject_enrichment`, `review_verdicts`, and unexpired auth `sessions`. A
transfer runs on the receiving side against a shipped snapshot of the source
DB; the artifact dirs move alongside by rsync (deploy.py, and `backup` below).

    uv run -m pyscripts userdb transfer --target <db> --incoming <db> --mode merge|mirror
    uv run -m pyscripts userdb snapshot --src <db> --dst <path>
    uv run -m pyscripts userdb backup --source live|alpha|local [--dest <dir>]

- transfer merge:  union rows; the source never clobbers the target (INSERT OR
        IGNORE, plus a NULL-safe exact-row guard so tables without a unique
        index, e.g. `email_consents`, stay duplicate-free on re-merge).
        Auto-id rows (`ledger_events`, `game_results`) drop their id so the
        target assigns fresh ones and dedup falls to the logical unique index.
        Decisions on rows both boxes hold are then reconciled by logical key
        (`_reconcile_decisions`): ledger moderation (a decided row beats a
        pending one, conflicting decisions keep the target's) and object
        review statuses (a decided row beats `new`; between two decided rows
        the later `updated_at` wins).
- transfer mirror: replace the target's copy of each table with the source's.
- snapshot: consistent hot copy of a live DB via SQLite's online backup API —
        the only shape in which a DB moves between boxes; rsync'ing the live
        file would miss un-checkpointed WAL commits and risk a torn image.
- backup: dated zstd DB snapshot + additive artifact-dir mirror under
        `<dest>/<source>/`, run on the machine that keeps the backups — the
        backed-up box keeps nothing durable. Bundles are immutable, so one
        growing mirror serves every snapshot: restoring day N = that day's DB
        + the mirror. Retention: last --keep-days daily snapshots plus every
        1st-of-month one forever. The daily timer installs via
        `pyscripts/services.py --backup-source live` on the machine holding
        the backups, never the backed-up box.

transfer/snapshot run on the serving box's runtime venv; the backup path
lazily imports deploy (cloud deps) for remote sources only.
"""

import re
import sqlite3
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import zstandard
from protocli import Dispatcher

from pyscripts import paths

TABLES = (
    "mcp_sessions",
    "mcp_objects",
    "game_results",
    "game_daily",
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

ZSTD_LEVEL = 19
BKP_TMP = f"{paths.DATA_DIR}/_bkxfer"
SNAP_RE = re.compile(r"rankless-(\d{8})\.sqlite\.zst")


def snapshot(src_db: str, dst: str) -> None:
    """Consistent copy of `src_db` at `dst` via SQLite's online backup API.

    Safe while a writer holds `src_db` open: reads a single consistent point and
    folds any WAL into `dst`, so `dst` is a standalone, fully-checkpointed file.
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
                _reconcile_decisions(
                    con,
                    "ledger_events",
                    keys=("orcid", "kind", "subject_hash"),
                    cols=("moderation", "moderated_by", "moderated_at"),
                    undecided="{a}.moderation = 'pending_review'",
                    decided="{a}.moderation IN (%s)"
                    % ", ".join(f"'{m}'" for m in DECIDED_MODERATIONS),
                    row_filter="{a}.revoked_at IS NULL",
                )
                _reconcile_decisions(
                    con,
                    "mcp_objects",
                    keys=("kind", "obj_key", "bundle"),
                    cols=("status", "status_note", "updated_at"),
                    undecided="{a}.status = 'new'",
                    decided="{a}.status != 'new'",
                    lww_col="updated_at",
                )
    finally:
        con.execute("DETACH DATABASE src")
        con.close()


def backup(
    *, source: str = "live", dest: str = "data/backups", keep_days: int = 7
) -> None:
    """Back up a source's user DB + artifact dirs into <dest>/<source>/
    (--source local|live|alpha; live/alpha resolve the running box via deploy).
    Prunes dated DB snapshots to --keep-days, keeping 1st-of-month ones forever."""
    root = Path(dest) / source
    db_dir = root / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    out = db_dir / f"rankless-{datetime.now(UTC).strftime('%Y%m%d')}.sqlite.zst"
    if source == "local":
        _backup_local(root, out)
    else:
        _backup_box(source, root, out)
    removed = prune(db_dir, keep_days)
    kept = len(list(db_dir.glob("rankless-*.sqlite.zst")))
    print(
        f"[backup] {out.name} ({out.stat().st_size // 1024} KiB) -> {root}; "
        f"{kept} snapshot(s) kept, {len(removed)} pruned"
    )


def prune(db_dir: Path, keep_days: int) -> list[str]:
    """Delete dated snapshots older than keep_days, except 1st-of-month ones."""
    cutoff = datetime.now(UTC).date() - timedelta(days=keep_days)
    removed = []
    for f in sorted(db_dir.iterdir()):
        m = SNAP_RE.fullmatch(f.name)
        if m is None:
            continue
        day = datetime.strptime(m.group(1), "%Y%m%d").date()
        if day.day == 1 or day >= cutoff:
            continue
        f.unlink()
        removed.append(f.name)
    if removed:
        print(f"[backup] pruned {', '.join(removed)}")
    return removed


def _transfer_table(con: sqlite3.Connection, table: str, mode: str) -> None:
    if not _has_table(con, "src", table):
        return
    _ensure_target_table(con, table)
    _align_src_columns(con, table)
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


def _reconcile_decisions(
    con: sqlite3.Connection,
    table: str,
    keys: tuple[str, ...],
    cols: tuple[str, ...],
    undecided: str,
    decided: str,
    lww_col: str | None = None,
    row_filter: str | None = None,
) -> None:
    """Post-merge decision propagation for rows both sides already hold,
    matched on `keys` (INSERT OR IGNORE never touches them, so a decision made
    on the source box would otherwise stay invisible here). `undecided` /
    `decided` / `row_filter` are SQL predicates over the `{a}` row alias;
    `cols` (decision column first) are copied from an incoming decided row
    onto an undecided target. Between two decided rows the target wins, unless
    `lww_col` orders the incoming row strictly later. Divergent decided pairs
    are warned either way."""
    if not (_has_table(con, "src", table) and _has_table(con, "main", table)):
        return
    m = f"main.{table}"
    on = " AND ".join(f"s.{k} = {m}.{k}" for k in keys)
    src_match = f"{on} AND {decided.format(a='s')}"
    if row_filter:
        src_match += f" AND {row_filter.format(a='s')}"
    takes = undecided.format(a=m)
    if lww_col:
        takes = f"({takes} OR s.{lww_col} > {m}.{lww_col})"
    _warn_divergent(con, table, keys, cols[0], decided, lww_col, row_filter)
    outer = f" AND {row_filter.format(a=m)}" if row_filter else ""
    con.execute(
        f"UPDATE {m} SET ({', '.join(cols)}) ="
        f" (SELECT {', '.join(f's.{c}' for c in cols)}"
        f"  FROM src.{table} s WHERE {src_match})"
        f" WHERE EXISTS (SELECT 1 FROM src.{table} s WHERE {src_match} AND {takes})"
        f"{outer}"
    )


def _warn_divergent(
    con: sqlite3.Connection,
    table: str,
    keys: tuple[str, ...],
    decision_col: str,
    decided: str,
    lww_col: str | None,
    row_filter: str | None,
) -> None:
    on = " AND ".join(f"s.{k} = t.{k}" for k in keys)
    conds = [decided.format(a="t"), decided.format(a="s")]
    if row_filter:
        conds += [row_filter.format(a="t"), row_filter.format(a="s")]
    newer = f"s.{lww_col} > t.{lww_col}" if lww_col else "0"
    rows = con.execute(
        f"SELECT {', '.join(f't.{k}' for k in keys)},"
        f" t.{decision_col}, s.{decision_col}, {newer}"
        f" FROM main.{table} t JOIN src.{table} s ON {on}"
        f" WHERE {' AND '.join(conds)} AND t.{decision_col} != s.{decision_col}"
    ).fetchall()
    for row in rows:
        key = "|".join(str(v) for v in row[:-3])
        kept, incoming, takes_incoming = row[-3:]
        winner, loser = (incoming, kept) if takes_incoming else (kept, incoming)
        print(
            f"warning: {table} decision conflict on {key}:"
            f" {winner!r} wins over {loser!r}",
            file=sys.stderr,
        )


def _align_src_columns(con: sqlite3.Connection, table: str) -> None:
    # A snapshot from a box on older code may lack columns the target's schema
    # has since grown; add them (NULL) to the attached throwaway copy so the
    # transfer SQL's target-side column list resolves on both schemas.
    src_cols = {r[1] for r in con.execute(f"PRAGMA src.table_info({table})")}
    for r in con.execute(f"PRAGMA main.table_info({table})"):
        if r[1] not in src_cols:
            con.execute(f"ALTER TABLE src.{table} ADD COLUMN {r[1]} {r[2]}")


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
    # Indexes too — merge dedup relies on the source's unique indexes.
    for (idx_sql,) in con.execute(
        "SELECT sql FROM src.sqlite_master"
        " WHERE type='index' AND tbl_name=? AND sql IS NOT NULL",
        (table,),
    ):
        con.execute(idx_sql)


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


def _backup_local(root: Path, out: Path) -> None:
    db = paths.db_path()
    if not Path(db).exists():
        raise SystemExit(f"no {db} in this checkout")
    with tempfile.TemporaryDirectory() as td:
        snap = Path(td) / "rankless.sqlite"
        snapshot(db, str(snap))
        _compress(snap, out)
    for rel in paths.MCP_ARTIFACT_RELS:
        if Path(rel).exists():
            subprocess.run(["rsync", "-ra", rel, f"{root}/"], check=True)


def _backup_box(source: str, root: Path, out: Path) -> None:
    # Lazy import: --source local must work on machines without the cloud
    # dependencies deploy.py pulls in (boto3 etc.).
    from pyscripts import deploy

    if source not in ("live", "alpha"):
        raise SystemExit("--source must be local, live, or alpha")
    tpr = deploy.get_running_tpr(live=source == "live")
    remote_db = f"{tpr.deploy_dir}/{paths.DB_REL}"
    if not tpr.ssh.remote_exists(remote_db):
        raise SystemExit(f"no DB at {remote_db} on the {source} box")
    remote_tmp = f"{tpr.deploy_dir}/{BKP_TMP}"
    tpr.ssh.run(f"rm -rf {remote_tmp} && mkdir -p {remote_tmp}")
    tpr.run_userdb(f"snapshot --src {paths.DB_REL} --dst {BKP_TMP}/rankless.sqlite")
    with tempfile.TemporaryDirectory() as td:
        tpr.ssh.rsync_from(f"{remote_tmp}/rankless.sqlite", td)
        tpr.ssh.run(f"rm -rf {remote_tmp}")
        _compress(Path(td) / "rankless.sqlite", out)
    for rel in paths.MCP_ARTIFACT_RELS:
        remote_dir = f"{tpr.deploy_dir}/{rel}"
        if tpr.ssh.remote_exists(remote_dir):
            tpr.ssh.rsync_from(remote_dir, str(root))


def _compress(src: Path, out: Path) -> None:
    out.write_bytes(zstandard.compress(src.read_bytes(), ZSTD_LEVEL))


def _transfer_cmd(*, target: str, incoming: str, mode: str) -> None:
    """Move the curated tables from --incoming into --target (--mode merge|mirror);
    runs on the receiving side against a shipped snapshot, see module docs."""
    transfer(target, incoming, mode)


def _snapshot_cmd(*, src: str, dst: str) -> None:
    """Consistent hot copy of --src at --dst (SQLite online backup API)."""
    snapshot(src, dst)


_dispatcher = Dispatcher(
    "pyscripts userdb",
    {
        "transfer": _transfer_cmd,
        "snapshot": _snapshot_cmd,
        "backup": backup,
    },
)
