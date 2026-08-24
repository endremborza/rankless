"""Unified store for MCP-derived objects: game cards, verified findings, and
whatever the miners produce next.

Payloads live in immutable per-run bundles — `data/mcp-objects/<run>.jsonl.zst`,
zstd-compressed, one self-describing JSON object per line — while `mcp_objects`
(`data/rankless.sqlite`) is a payload-free index: logical key `(kind, obj_key)`,
the `(bundle, line)` address, generation stamp, review `status`
(new → approved/rejected), and denormalized display fields. Regeneration never
rewrites anything: a later run's bundle adds a superseding version row, and
consumers read the latest non-rejected version per key. `gen_at` is a sortable
UTC ISO datetime, stamped here at write time (`ingest --gen-at` overrides it for
historical backfills). Bundles move between boxes with the `data/mcp-sessions/`
artifact copy; index rows ride the user-DB handoff (`pyscripts/mcp_db.py`) where
merges dedup on `(kind, obj_key, bundle)` and review decisions propagate. The
frontend reads the same table + bundles via `src/lib/server/objects.ts`
(`/game` consumes cards, `/mcp` reviews/presents).

    uv run -m pyscripts objects list --kind game-card
    uv run -m pyscripts objects ingest --path run.jsonl.zst
    uv run -m pyscripts objects export --kind game-card --path out.jsonl.zst
    uv run -m pyscripts objects set-status --ids 3,4 --status approved
    uv run -m pyscripts objects fsck
"""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import zstandard
from protocli import Dispatcher

from pyscripts.paths import DB_REL, MCP_OBJECTS_REL

STATUSES = ("new", "approved", "rejected")
ZSTD_LEVEL = 19

SCHEMA = """
CREATE TABLE IF NOT EXISTS mcp_objects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    obj_key TEXT NOT NULL,
    bundle TEXT NOT NULL,
    line INTEGER NOT NULL,
    gen_at TEXT NOT NULL,
    etype TEXT,
    sem_id TEXT,
    title TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    status_note TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_obj_version ON mcp_objects(kind, obj_key, bundle);
CREATE INDEX IF NOT EXISTS idx_obj_kind_status ON mcp_objects(kind, status);
"""

_CURRENT_SQL = """
SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY kind, obj_key ORDER BY gen_at DESC, bundle DESC
    ) AS rn FROM mcp_objects WHERE kind = ? AND status != 'rejected'
) WHERE rn = 1 ORDER BY obj_key
"""


def bundles_root() -> Path:
    return Path(MCP_OBJECTS_REL)


def bundle_path(run: str) -> Path:
    return bundles_root() / f"{run}.jsonl.zst"


def utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(db_path: str = DB_REL) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA busy_timeout = 30000")
    con.execute("PRAGMA journal_mode = WAL")
    con.executescript(SCHEMA)
    # CREATE IF NOT EXISTS never extends an existing table; added columns need
    # an explicit migration for DBs created under the older schema.
    cols = {r[1] for r in con.execute("PRAGMA table_info(mcp_objects)")}
    if "status_note" not in cols:
        con.execute("ALTER TABLE mcp_objects ADD COLUMN status_note TEXT")
    return con


def write_bundle(
    con: sqlite3.Connection, run: str, objects: list[dict], gen_at: str = ""
) -> int:
    """Write `<run>.jsonl.zst` (immutable — refuses to overwrite) and index
    every object; returns the number of indexed rows."""
    if not objects:
        return 0
    fields = ("kind", "obj_key", "etype", "sem_id", "title", "payload")
    objects = [{k: o.get(k) for k in fields} for o in objects]
    stamp = gen_at or utc_now_iso()
    path = bundle_path(run)
    raw = "".join(json.dumps(o, sort_keys=True) + "\n" for o in objects).encode()
    if path.exists():
        if zstandard.decompress(path.read_bytes()) != raw:
            raise SystemExit(f"bundle {path} exists with different content")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(zstandard.compress(raw, ZSTD_LEVEL))
    with con:
        for line, obj in enumerate(objects):
            con.execute(
                "INSERT OR IGNORE INTO mcp_objects"
                " (kind, obj_key, bundle, line, gen_at, etype, sem_id, title)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    obj["kind"],
                    obj["obj_key"],
                    run,
                    line,
                    stamp,
                    obj.get("etype"),
                    obj.get("sem_id"),
                    obj.get("title"),
                ),
            )
    return len(objects)


def read_bundle(run: str) -> list[dict]:
    raw = zstandard.decompress(bundle_path(run).read_bytes())
    return [json.loads(line) for line in raw.decode().splitlines()]


def read_entries(row_list: list[dict]) -> list[dict]:
    """The stored objects for index rows, decompressing each bundle once."""
    bundles = {b: read_bundle(b) for b in {r["bundle"] for r in row_list}}
    return [bundles[r["bundle"]][r["line"]] for r in row_list]


def current(con: sqlite3.Connection, kind: str) -> list[dict]:
    """Latest non-rejected version per logical key."""
    return _dicts(con.execute(_CURRENT_SQL, (kind,)))


def rows(con: sqlite3.Connection, kind: str = "", status: str = "") -> list[dict]:
    conds, params = [], []
    for col, val in (("kind", kind), ("status", status)):
        if val:
            conds.append(f"{col} = ?")
            params.append(val)
    where = f" WHERE {' AND '.join(conds)}" if conds else ""
    return _dicts(con.execute(f"SELECT * FROM mcp_objects{where} ORDER BY id", params))


def _dicts(cur: sqlite3.Cursor) -> list[dict]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def list_cmd(*, kind: str = "", status: str = "", db: str = DB_REL) -> None:
    """List indexed object versions (--kind / --status filters)."""
    con = connect(db)
    try:
        for r in rows(con, kind, status):
            note = f"  [{r['status_note']}]" if r.get("status_note") else ""
            print(
                f"{r['id']:>5}  {r['kind']:<10} {r['status']:<9} "
                f"{r['obj_key']:<36} {r['bundle']:<32} {r['title'] or ''}{note}"
            )
    finally:
        con.close()


def ingest(*, path: str, run: str = "", gen_at: str = "", db: str = DB_REL) -> None:
    """Ingest a bundle file (.jsonl or .jsonl.zst of {kind, obj_key, payload, ...}
    objects) into the store under --run (default: the file's stem)."""
    src = Path(path)
    raw = src.read_bytes()
    if src.name.endswith(".zst"):
        raw = zstandard.decompress(raw)
    objects = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    name = run or src.name.removesuffix(".zst").removesuffix(".jsonl")
    con = connect(db)
    try:
        n = write_bundle(con, name, objects, gen_at)
    finally:
        con.close()
    print(f"{n} object(s) indexed from bundle {name!r}")


def export(*, path: str, kind: str = "", status: str = "", db: str = DB_REL) -> None:
    """Export indexed objects with payloads as re-ingestable JSONL; a .zst
    --path compresses (preferred — raw JSONL is for ad-hoc inspection only)."""
    con = connect(db)
    try:
        selected = rows(con, kind, status)
        out = [
            json.dumps(
                {**entry, "status": r["status"], "status_note": r["status_note"]}
            )
            for r, entry in zip(selected, read_entries(selected))
        ]
    finally:
        con.close()
    data = "".join(line + "\n" for line in out)
    if path.endswith(".zst"):
        Path(path).write_bytes(zstandard.compress(data.encode(), ZSTD_LEVEL))
    else:
        Path(path).write_text(data)
    print(f"{len(out)} object(s) -> {path}")


def set_status(*, ids: str, status: str, note: str = "", db: str = DB_REL) -> None:
    """Set review status (--ids comma list, --status new|approved|rejected);
    a rejection requires --note — the reason is kept for later review."""
    if status not in STATUSES:
        raise SystemExit(f"status must be one of {STATUSES}")
    if status == "rejected" and not note.strip():
        raise SystemExit("rejecting requires --note (why, for later review)")
    id_list = [int(i) for i in ids.split(",") if i.strip()]
    con = connect(db)
    try:
        with con:
            n = con.execute(
                f"UPDATE mcp_objects SET status = ?, status_note = ?,"
                f" updated_at = datetime('now')"
                f" WHERE id IN ({','.join('?' * len(id_list))})",
                (status, note.strip() or None, *id_list),
            ).rowcount
    finally:
        con.close()
    print(f"{n} object(s) -> {status}")


def fsck(*, db: str = DB_REL) -> None:
    """Verify every index row's (bundle, line) resolves to a stored object and
    report unreferenced bundle files; exits 1 on dangling rows."""
    con = connect(db)
    try:
        all_rows = rows(con)
    finally:
        con.close()
    lengths: dict[str, int] = {}
    for name in {r["bundle"] for r in all_rows}:
        try:
            lengths[name] = len(read_bundle(name))
        except FileNotFoundError:
            lengths[name] = -1
    problems = []
    for r in all_rows:
        n = lengths[r["bundle"]]
        ref = f"row {r['id']} ({r['kind']}|{r['obj_key']})"
        if n < 0:
            problems.append(f"{ref}: bundle {r['bundle']!r} missing on disk")
        elif r["line"] >= n:
            problems.append(f"{ref}: line {r['line']} beyond bundle size {n}")
    for p in problems:
        print(f"DANGLING {p}")
    for f in sorted(bundles_root().glob("*.jsonl.zst")):
        if f.name.removesuffix(".jsonl.zst") not in lengths:
            print(f"note: bundle {f.name} on disk but unreferenced by the index")
    if problems:
        raise SystemExit(1)
    print(f"ok: {len(all_rows)} row(s) across {len(lengths)} bundle(s)")


_dispatcher = Dispatcher(
    "pyscripts objects",
    {
        "list": list_cmd,
        "ingest": ingest,
        "export": export,
        "set-status": set_status,
        "fsck": fsck,
    },
)
