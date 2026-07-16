import sqlite3
from pathlib import Path

from pyscripts import mcp_db

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

    mcp_db.transfer(str(dst), str(src), "merge")
    assert _counts(dst) == {"ledger_events": 1, "email_consents": 1, "sessions": 1}

    # re-merge: no duplicates, including the unique-index-less email_consents
    mcp_db.transfer(str(dst), str(src), "merge")
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

    mcp_db.transfer(str(dst), str(src), "merge")
    assert _counts(dst)["ledger_events"] == 2


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

    mcp_db.transfer(str(dst), str(src), "mirror")
    con = sqlite3.connect(dst)
    assert con.execute("SELECT token FROM sessions").fetchall() == [("live-tok",)]
    con.close()
