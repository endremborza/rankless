import json

import pytest

from pyscripts.ledger_ids import canonical_doi, normalize_orcid
from pyscripts.review_ledger import (
    Claim,
    build_bundle,
    connect,
    load_enrichment,
    select_claims,
    validate_verdicts,
)

ORCID = "0000-0002-1247-296X"
DOI = "10.1126/sciadv.abc0764"


@pytest.fixture
def con(tmp_path):
    con = connect(str(tmp_path / "test.sqlite"))
    con.executescript(
        """
        CREATE TABLE ledger_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            orcid TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL,
            subject_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            revoked_at TEXT, moderation TEXT NOT NULL DEFAULT 'auto_ok',
            moderated_by TEXT, moderated_at TEXT
        );
        CREATE TABLE subject_enrichment (
            source TEXT NOT NULL, key TEXT NOT NULL, status TEXT NOT NULL,
            data TEXT, fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (source, key)
        );
        """
    )
    return con


def add_claim(con, event_id: int, doi: str, moderation: str = "pending_review") -> None:
    payload = {"kind": "claim_paper", "work": {"doi": doi}}
    con.execute(
        "INSERT INTO ledger_events (event_id, orcid, kind, payload, subject_hash, moderation)"
        " VALUES (?, ?, 'claim_paper', ?, ?, ?)",
        (event_id, ORCID, json.dumps(payload), f"h{event_id}", moderation),
    )


def add_enrichment(
    con, source: str, key: str, status: str = "ok", data: dict | None = None
):
    con.execute(
        "INSERT INTO subject_enrichment (source, key, status, data) VALUES (?, ?, ?, ?)",
        (source, key, status, json.dumps(data) if data else None),
    )


def add_verdict(con, subject_hash: str, model: str = "sonnet") -> None:
    con.execute(
        "INSERT INTO review_verdicts"
        " (orcid, kind, subject_hash, model, verdict, confidence, reasoning, created_at)"
        " VALUES (?, 'claim_paper', ?, ?, 'unsure', 0.5, 'r', '2026-07-01T00:00:00Z')",
        (ORCID, subject_hash, model),
    )


def test_normalizers():
    assert normalize_orcid("https://orcid.org/0000-0002-1247-296x") == ORCID
    assert canonical_doi("https://doi.org/10.1126/SCIADV.ABC0764") == DOI


def test_selection_skips_verdict_bearing_subjects(con):
    add_claim(con, 1, DOI)
    add_claim(con, 2, "10.1/other")
    add_claim(con, 3, "10.1/decided", moderation="accepted")
    add_verdict(con, "h1")
    picked = select_claims(con, "sonnet", "claim_paper", None, force=False)
    assert [c.event_id for c in picked] == [2]
    forced = select_claims(con, "sonnet", "claim_paper", None, force=True)
    assert [c.event_id for c in forced] == [1, 2]
    other_model = select_claims(con, "opus", "claim_paper", None, force=False)
    assert [c.event_id for c in other_model] == [1, 2]


def test_selection_rejects_other_kinds(con):
    with pytest.raises(SystemExit, match="unsupported kind"):
        select_claims(con, "sonnet", "disown_paper", None, force=False)


def test_enrichment_gate_lists_missing_pairs(con):
    claims = [Claim(1, ORCID, "claim_paper", "h1", DOI)]
    add_enrichment(con, "crossref", DOI, "ok", {"authors": []})
    add_enrichment(con, "orcid", ORCID, "error")  # error counts as missing
    with pytest.raises(SystemExit) as exc:
        load_enrichment(con, claims)
    msg = str(exc.value)
    assert f"(openalex, {DOI})" in msg
    assert f"(orcid, {ORCID})" in msg
    assert f"(crossref, {DOI})" not in msg
    assert "Fetch metadata" in msg


def test_bundle_flags_doi_on_orcid_record(con):
    claims = [Claim(1, ORCID, "claim_paper", "h1", DOI)]
    add_enrichment(con, "crossref", DOI, "not_found")
    add_enrichment(con, "openalex", DOI, "ok", {"title": "t", "authors": []})
    add_enrichment(
        con,
        "orcid",
        ORCID,
        "ok",
        {"name": "C. Hidalgo", "work_dois": [DOI], "work_titles": ["t"], "n_works": 1},
    )
    bundle = build_bundle(claims, load_enrichment(con, claims))
    assert bundle["claimant"]["orcid_name"] == "C. Hidalgo"
    claim = bundle["claims"][0]
    assert claim["id"] == "1"
    assert claim["crossref"] is None  # not_found → no record, still usable evidence
    assert claim["openalex"]["title"] == "t"
    assert claim["doi_on_orcid_record"] is True


def test_validate_verdicts():
    claims = [
        Claim(1, ORCID, "claim_paper", "h1", DOI),
        Claim(2, ORCID, "claim_paper", "h2", DOI),
    ]
    good = {
        "verdicts": [
            {"id": "2", "verdict": "reject", "confidence": 0.8, "reasoning": "nope"},
            {"id": "1", "verdict": "approve", "confidence": 0.95, "reasoning": "yes"},
        ]
    }
    ordered = validate_verdicts(good, claims)
    assert [v["id"] for v in ordered] == ["1", "2"]  # reordered to claim order

    for bad, msg in [
        ({"verdicts": [good["verdicts"][0]]}, "missing verdicts"),
        ({"verdicts": good["verdicts"] + [good["verdicts"][0]]}, "duplicate"),
        (
            {
                "verdicts": [
                    {**good["verdicts"][0], "verdict": "maybe"},
                    good["verdicts"][1],
                ]
            },
            "verdict",
        ),
        (
            {
                "verdicts": [
                    {**good["verdicts"][0], "confidence": 1.5},
                    good["verdicts"][1],
                ]
            },
            "confidence",
        ),
        (
            {
                "verdicts": [
                    {**good["verdicts"][0], "reasoning": " "},
                    good["verdicts"][1],
                ]
            },
            "reasoning",
        ),
        ([], "verdicts"),
    ]:
        with pytest.raises(ValueError, match=msg):
            validate_verdicts(bad, claims)


def test_insert_dedup_via_unique_index(con):
    row = (
        ORCID,
        "claim_paper",
        "h1",
        "sonnet",
        "approve",
        0.9,
        "r",
        None,
        "2026-07-10T00:00:00Z",
    )
    ins = (
        "INSERT OR IGNORE INTO review_verdicts"
        " (orcid, kind, subject_hash, model, verdict, confidence, reasoning, checks, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    con.execute(ins, row)
    con.execute(
        ins, row
    )  # same batch stamp → deduped, as after a cross-box double merge
    assert con.execute("SELECT count(*) FROM review_verdicts").fetchone()[0] == 1


def test_connect_schema_matches_app_ddl(con):
    cols = [r[1] for r in con.execute("PRAGMA table_info(review_verdicts)")]
    assert cols == [
        "verdict_id",
        "orcid",
        "kind",
        "subject_hash",
        "model",
        "verdict",
        "confidence",
        "reasoning",
        "checks",
        "created_at",
    ]


def test_batches_group_by_claimant():
    from pyscripts.review_ledger import batches

    claims = [
        Claim(i, orcid, "claim_paper", f"h{i}", DOI)
        for i, orcid in [(1, "A"), (2, "B"), (3, "A"), (4, "A")]
    ]
    got = batches(claims, size=2)
    assert [[c.event_id for c in g] for g in got] == [[1, 3], [4], [2]]
