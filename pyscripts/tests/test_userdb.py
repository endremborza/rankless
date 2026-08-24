import sqlite3
from pathlib import Path

from pyscripts import userdb

LEDGER_DDL = """
CREATE TABLE ledger_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    orcid TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    subject_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    revoked_at TEXT,
    moderation TEXT NOT NULL DEFAULT 'auto_ok',
    moderated_by TEXT,
    moderated_at TEXT
);
CREATE UNIQUE INDEX idx_le_dedup
    ON ledger_events(orcid, kind, subject_hash)
    WHERE revoked_at IS NULL;
CREATE TABLE email_consents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    orcid TEXT NOT NULL,
    email TEXT NOT NULL,
    email_source TEXT NOT NULL DEFAULT 'manual',
    purposes TEXT NOT NULL,
    consent_version TEXT NOT NULL,
    granted_at TEXT NOT NULL DEFAULT (datetime('now')),
    withdrawn_at TEXT
);
CREATE TABLE sessions (
    token TEXT PRIMARY KEY,
    orcid TEXT NOT NULL,
    name TEXT NOT NULL,
    semantic_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL
);
"""


def _make_db(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.executescript(LEDGER_DDL)
    return con


def _seed_source(con: sqlite3.Connection) -> None:
    con.execute(
        "INSERT INTO ledger_events (orcid, kind, payload, subject_hash) "
        "VALUES ('0000-1', 'disown_paper', '{}', 'h1')"
    )
    con.execute(
        "INSERT INTO email_consents (orcid, email, purposes, consent_version) "
        "VALUES ('0000-1', 'a@b.c', '[\"news\"]', 'v1')"
    )
    con.execute(
        "INSERT INTO sessions (token, orcid, name, expires_at) "
        "VALUES ('live-tok', '0000-1', 'A', datetime('now', '+300 days'))"
    )
    con.execute(
        "INSERT INTO sessions (token, orcid, name, expires_at) "
        "VALUES ('dead-tok', '0000-1', 'A', datetime('now', '-1 day'))"
    )
    con.commit()


def _counts(path: Path) -> dict[str, int]:
    con = sqlite3.connect(path)
    try:
        return {
            t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            for t in ("ledger_events", "email_consents", "sessions")
        }
    finally:
        con.close()


def test_merge_moves_user_tables_and_is_idempotent(tmp_path: Path) -> None:
    src, dst = tmp_path / "src.sqlite", tmp_path / "dst.sqlite"
    _seed_source(_make_db(src))
    _make_db(dst).close()

    userdb.transfer(str(dst), str(src), "merge")
    assert _counts(dst) == {"ledger_events": 1, "email_consents": 1, "sessions": 1}

    # re-merge: no duplicates, including the unique-index-less email_consents
    userdb.transfer(str(dst), str(src), "merge")
    assert _counts(dst) == {"ledger_events": 1, "email_consents": 1, "sessions": 1}

    con = sqlite3.connect(dst)
    assert con.execute("SELECT token FROM sessions").fetchall() == [("live-tok",)]
    con.close()


def test_merge_keeps_target_rows(tmp_path: Path) -> None:
    src, dst = tmp_path / "src.sqlite", tmp_path / "dst.sqlite"
    _seed_source(_make_db(src))
    dst_con = _make_db(dst)
    dst_con.execute(
        "INSERT INTO ledger_events (orcid, kind, payload, subject_hash) "
        "VALUES ('0000-2', 'disown_paper', '{}', 'h2')"
    )
    dst_con.commit()
    dst_con.close()

    userdb.transfer(str(dst), str(src), "merge")
    assert _counts(dst)["ledger_events"] == 2


def _insert_event(
    con: sqlite3.Connection,
    subject_hash: str,
    moderation: str,
    moderated_by: str | None = None,
) -> None:
    con.execute(
        "INSERT INTO ledger_events "
        "(orcid, kind, payload, subject_hash, moderation, moderated_by, moderated_at) "
        "VALUES ('0000-1', 'claim_paper', '{}', ?, ?, ?, ?)",
        (
            subject_hash,
            moderation,
            moderated_by,
            "2026-08-14T00:00:00Z" if moderated_by else None,
        ),
    )


def test_merge_reconciles_moderation(tmp_path: Path) -> None:
    src, dst = tmp_path / "src.sqlite", tmp_path / "dst.sqlite"
    src_con = _make_db(src)
    _insert_event(src_con, "h1", "accepted", "0000-admin")
    _insert_event(src_con, "h2", "rejected", "0000-admin")
    _insert_event(src_con, "h3", "pending_review")
    src_con.commit()
    src_con.close()

    dst_con = _make_db(dst)
    _insert_event(dst_con, "h1", "pending_review")
    _insert_event(dst_con, "h2", "accepted", "0000-other")  # decided never reverts
    _insert_event(dst_con, "h3", "auto_ok", "auto:doi-authorship")
    dst_con.commit()
    dst_con.close()

    userdb.transfer(str(dst), str(src), "merge")

    con = sqlite3.connect(dst)
    rows = dict(
        con.execute(
            "SELECT subject_hash, moderation || '|' || coalesce(moderated_by, '') "
            "FROM ledger_events"
        ).fetchall()
    )
    con.close()
    assert len(rows) == 3  # reconciled in place, no duplicate inserts
    assert rows["h1"] == "accepted|0000-admin"  # pending target takes the decision
    assert rows["h2"] == "accepted|0000-other"  # conflicting decision keeps target
    assert (
        rows["h3"] == "auto_ok|auto:doi-authorship"
    )  # incoming pending changes nothing


def test_mirror_replaces_and_drops_expired_sessions(tmp_path: Path) -> None:
    src, dst = tmp_path / "src.sqlite", tmp_path / "dst.sqlite"
    _seed_source(_make_db(src))
    dst_con = _make_db(dst)
    dst_con.execute(
        "INSERT INTO sessions (token, orcid, name, expires_at) "
        "VALUES ('target-tok', '0000-9', 'B', datetime('now', '+300 days'))"
    )
    dst_con.commit()
    dst_con.close()

    userdb.transfer(str(dst), str(src), "mirror")
    con = sqlite3.connect(dst)
    assert con.execute("SELECT token FROM sessions").fetchall() == [("live-tok",)]
    con.close()


OBJECTS_DDL = """
CREATE TABLE mcp_objects (
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
CREATE UNIQUE INDEX idx_obj_version ON mcp_objects(kind, obj_key, bundle);
"""


def _insert_obj(
    con: sqlite3.Connection,
    obj_key: str,
    status: str,
    note: str | None,
    updated_at: str,
) -> None:
    con.execute(
        "INSERT INTO mcp_objects"
        " (kind, obj_key, bundle, line, gen_at, status, status_note, updated_at)"
        " VALUES ('game-card', ?, 'b1', 0, '2026-01-01', ?, ?, ?)",
        (obj_key, status, note, updated_at),
    )


def test_merge_reconciles_object_status_lww(tmp_path: Path) -> None:
    src, dst = tmp_path / "src.sqlite", tmp_path / "dst.sqlite"
    src_con = sqlite3.connect(src)
    src_con.executescript(OBJECTS_DDL)
    _insert_obj(src_con, "k1", "approved", None, "2026-08-02T00:00:00Z")
    _insert_obj(src_con, "k2", "rejected", "stale fact", "2026-08-03T00:00:00Z")
    _insert_obj(src_con, "k3", "approved", None, "2026-08-02T00:00:00Z")
    _insert_obj(src_con, "k4", "new", None, "2026-08-09T00:00:00Z")
    src_con.commit()
    src_con.close()

    dst_con = sqlite3.connect(dst)
    dst_con.executescript(OBJECTS_DDL)
    _insert_obj(dst_con, "k1", "new", None, "2026-08-01T00:00:00Z")
    _insert_obj(dst_con, "k2", "approved", None, "2026-08-02T00:00:00Z")
    _insert_obj(dst_con, "k3", "rejected", "leaky clue", "2026-08-03T00:00:00Z")
    _insert_obj(dst_con, "k4", "approved", None, "2026-08-02T00:00:00Z")
    dst_con.commit()
    dst_con.close()

    userdb.transfer(str(dst), str(src), "merge")

    con = sqlite3.connect(dst)
    rows = dict(
        con.execute(
            "SELECT obj_key, status || '|' || coalesce(status_note, '')"
            " FROM mcp_objects"
        ).fetchall()
    )
    con.close()
    assert len(rows) == 4  # reconciled in place, no duplicate inserts
    assert rows["k1"] == "approved|"  # new target takes the decision
    assert rows["k2"] == "rejected|stale fact"  # later incoming decision wins
    assert rows["k3"] == "rejected|leaky clue"  # earlier incoming decision loses
    assert rows["k4"] == "approved|"  # incoming new never reverts a decision


def test_prune_keeps_recent_and_month_firsts(tmp_path: Path) -> None:
    from datetime import UTC, datetime, timedelta

    today = datetime.now(UTC).date()
    old = today - timedelta(days=20)
    if old.day == 1:
        old -= timedelta(days=1)
    names = {
        f"rankless-{today:%Y%m%d}.sqlite.zst": True,
        f"rankless-{today - timedelta(days=3):%Y%m%d}.sqlite.zst": True,
        f"rankless-{old:%Y%m%d}.sqlite.zst": False,
        f"rankless-{old.replace(day=1):%Y%m%d}.sqlite.zst": True,
        "not-a-snapshot.txt": True,
    }
    for name in names:
        (tmp_path / name).touch()

    removed = userdb.prune(tmp_path, keep_days=7)

    assert set(removed) == {n for n, kept in names.items() if not kept}
    assert {f.name for f in tmp_path.iterdir()} == {
        n for n, kept in names.items() if kept
    }
