import json
import sqlite3
from pathlib import Path

from pyscripts import claims
from pyscripts.ledger_ids import merge_subject_hash, author_subject

SCHEMA = """
CREATE TABLE ledger_events (
  event_id INTEGER PRIMARY KEY AUTOINCREMENT,
  orcid TEXT, kind TEXT, payload TEXT, subject_hash TEXT,
  moderation TEXT DEFAULT 'pending_review', moderated_by TEXT, moderated_at TEXT,
  revoked_at TEXT
);
"""


def _claim(con: sqlite3.Connection, orcid: str, doi: str, subject_hash: str) -> None:
    con.execute(
        "INSERT INTO ledger_events (orcid, kind, payload, subject_hash) "
        "VALUES (?, 'claim_paper', ?, ?)",
        (orcid, json.dumps({"work": {"doi": doi}}), subject_hash),
    )


def _seed(tmp_path: Path) -> tuple[str, dict]:
    db = str(tmp_path / "ledger.sqlite")
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    _claim(con, "0000-0001", "10.1/landed", "aa")
    _claim(con, "0000-0002", "https://doi.org/10.1/REJECTED", "bb")
    _claim(con, "0000-0003", "10.1/no-authors", "cc")
    con.commit()
    con.close()

    ul = tmp_path / "user-ledger"
    ul.mkdir()
    (ul / "snapshot_manifest.json").write_text(json.dumps({"run_id": "2026-08-15T01Z"}))
    (ul / "applied_manifest.json").write_text(
        json.dumps({"applied_keys": ["0000-0001|claim_paper|aa"]})
    )
    plan = {
        "claims": [
            {
                "orcid": "0000-0001",
                "name": "A",
                "doi": "10.1/landed",
                "verdict": "direct",
                "reason": "",
                "keep": "A1",
                "work_authors": ["A1"],
            },
            {
                "orcid": "0000-0002",
                "name": "B",
                "doi": "10.1/rejected",
                "verdict": "merge",
                "reason": "",
                "keep": "A2",
                "work_authors": ["A9"],
                "merge_candidates": ["A9"],
                "merge": {"drop": "A9", "decision": "rejected", "note": "other person"},
            },
            {
                "orcid": "0000-0003",
                "name": "C",
                "doi": "10.1/no-authors",
                "verdict": "unreachable",
                "reason": "oa_id_not_in_dataset",
                "keep": "A3",
                "work_authors": [],
            },
        ]
    }
    return db, plan


def test_record_accounts_for_every_claim(tmp_path: Path) -> None:
    db, plan = _seed(tmp_path)

    rec = claims.build_record(plan, tmp_path, db)

    assert (rec["submitted"], rec["applied"], rec["unresolved"]) == (3, 1, 2)
    # a rejected identity match and a work with no author records are distinct causes,
    # and neither is an internal skip-reason identifier
    assert rec["unresolved_by_cause"] == {
        claims.CAUSES["identity_match_rejected"]: 1,
        claims.CAUSES["oa_id_not_in_dataset"]: 1,
    }
    assert (rec["merges_reviewed"], rec["merges_approved"]) == (1, 0)
    assert [d["applied"] for d in rec["detail"]] == [True, False, False]


def test_accept_only_takes_what_the_snapshot_proves(tmp_path: Path) -> None:
    db, plan = _seed(tmp_path)

    assert claims.accept(plan=str(_write(tmp_path, plan)), db=db) == 1

    con = sqlite3.connect(db)
    accepted = dict(
        con.execute(
            "SELECT orcid, moderation FROM ledger_events WHERE kind = 'claim_paper'"
        )
    )
    con.close()
    assert accepted == {
        "0000-0001": "accepted",
        "0000-0002": "pending_review",
        "0000-0003": "pending_review",
    }


def test_merge_lane_writes_only_approved_decisions(tmp_path: Path) -> None:
    db, plan = _seed(tmp_path)
    plan["claims"][1]["merge"] = {"drop": "A9", "decision": "approved", "note": ""}
    plan_path = _write(tmp_path, plan)

    claims.apply_merges(admin_orcid="0000-9999", plan=str(plan_path), db=db)
    # the approved merge now credits the claimant, so their claim becomes acceptable
    assert claims.accept(plan=str(plan_path), db=db) == 2

    con = sqlite3.connect(db)
    rows = con.execute(
        "SELECT orcid, subject_hash, moderation, moderated_by FROM ledger_events "
        "WHERE kind = 'merge_authors'"
    ).fetchall()
    con.close()
    keep = author_subject(2, "0000-0002", "B")
    assert rows == [
        (
            "0000-0002",
            merge_subject_hash(keep, author_subject(9, None, "")),
            "accepted",
            "convert:0000-9999",
        )
    ]

    # idempotent: a second pass inserts nothing
    claims.apply_merges(admin_orcid="0000-9999", plan=str(plan_path), db=db)
    con = sqlite3.connect(db)
    assert (
        con.execute(
            "SELECT count(*) FROM ledger_events WHERE kind = 'merge_authors'"
        ).fetchone()[0]
        == 1
    )
    con.close()


def _write(tmp_path: Path, plan: dict) -> Path:
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    return path
