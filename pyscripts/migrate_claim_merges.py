"""One-time migration: convert claim merge-candidates into accepted merge_authors events.

A claim whose DOI is OA-attributed to a *name-matching other author record* cannot be
satisfied by the forced-oeuvre pass alone: the claimant's own author record is not on the
work. The resolution is an author merge (claimant keeps, matched record drops) — the ledger
stays the single mechanism, the pipeline's alias resolution then pulls the drop-record's
works into the claimant's oeuvre, and the claim resolves with zero claim-specific code.

Reads `merge_candidate` rows from a claims-measure JSON, prints the evidence per candidate
(claimant name/ORCID, work title + author list from the `subject_enrichment` cache, matched
OA record link), and requires an explicit y/n — a wrong author-merge is the highest-damage
event we can write, so the admin eyeballs every one. On yes, inserts a `merge_authors`
event with actor = claimant, moderation `accepted`, `moderated_by = 'convert:<admin>'`.

Candidates with no usable match id or no claimant OA record are printed and skipped (they
fall to the synthesis tail). Run once on the driver against the pulled DB, then
`merge_db_to_live` (new rows insert cleanly).

    uv run -m pyscripts.migrate_claim_merges --measure PATH --admin-orcid ORCID [--db PATH]
"""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from pyscripts import paths
from pyscripts.ledger_ids import canonical_doi

WORK_SOURCES = ("openalex", "crossref")


def author_canonical_key(subject: dict[str, Any]) -> str:
    # Mirror of authorCanonicalKey in src/lib/server/ledger-hash.ts.
    if subject.get("orcid"):
        return f"orcid:{subject['orcid']}"
    return f"oa:{subject['oa_id']}"


def merge_subject_hash(keep: dict[str, Any], drop: dict[str, Any]) -> str:
    # Mirror of subjectHash({kind:'merge_authors', ...}) in src/lib/server/ledger-hash.ts.
    keys = sorted([author_canonical_key(keep), author_canonical_key(drop)])
    return hashlib.sha1("|".join(keys).encode()).hexdigest()


def author_subject(oa_id: int, orcid: str | None, display_name: str) -> dict[str, Any]:
    # Mirror of TS AuthorSubject (src/lib/types/ledger.ts).
    return {
        "oa_id": oa_id,
        "orcid": orcid,
        "dm_id_at_creation": None,
        "semantic_id_at_creation": None,
        "run_id_at_creation": None,
        "display_snapshot": {"display_name": display_name},
    }


def oa_numeric(oa_author_id: str) -> int:
    return int(oa_author_id.lstrip("AW"))


def work_evidence(con: sqlite3.Connection, doi: str) -> str:
    for source in WORK_SOURCES:
        row = con.execute(
            "SELECT data FROM subject_enrichment WHERE source = ? AND key = ? AND status = 'ok'",
            (source, canonical_doi(doi)),
        ).fetchone()
        if row and row[0]:
            record = json.loads(row[0])
            authors = ", ".join(a["name"] for a in record.get("authors") or [])
            return f"  title:   {record.get('title')} ({record.get('year')}, {source})\n  authors: {authors}"
    return "  (no enrichment cached — run 'Fetch metadata' on /admin/ledger for the title/author list)"


def convert(measure_path: Path, db_path: str, admin_orcid: str) -> None:
    measure = json.loads(measure_path.read_text())
    claimants: dict[str, dict[str, Any]] = measure["authors"]
    candidates = [c for c in measure["claims"] if c.get("bucket") == "merge_candidate"]
    print(f"{len(candidates)} merge candidate(s) in {measure_path}")

    con = sqlite3.connect(db_path)
    con.execute("PRAGMA busy_timeout = 30000")
    inserted = skipped = 0
    try:
        for cand in candidates:
            orcid, doi = cand["orcid"], cand["doi"]
            match_ids = [m for m in cand.get("match_author_ids", []) if m]
            claimant = claimants.get(orcid)
            header = f"\nclaim {orcid} → {doi}"
            if claimant is None:
                print(
                    f"{header}\n  SKIP: claimant has no OA author record (no keep side)"
                )
                skipped += 1
                continue
            if not match_ids:
                print(f"{header}\n  SKIP: matched authorship has no OA author id")
                skipped += 1
                continue
            for match_id in match_ids:
                keep = author_subject(
                    oa_numeric(claimant["oa_id"]), orcid, claimant["name"]
                )
                drop = author_subject(oa_numeric(match_id), None, "")
                if keep["oa_id"] == drop["oa_id"]:
                    print(f"{header}\n  SKIP: matched record is the claimant's own")
                    skipped += 1
                    continue
                print(header)
                print(
                    f"  claimant: {claimant['name']} ({orcid}) — keeps "
                    f"https://openalex.org/{claimant['oa_id']} "
                    f"({claimant['works']} works, {claimant['cites']} cites)"
                )
                print(
                    f"  drops:    https://openalex.org/{match_id} "
                    f"(the record OA credits for this {cand.get('type')}, {cand.get('year')})"
                )
                print(work_evidence(con, doi))
                if input("  merge? [y/N] ").strip().lower() != "y":
                    print("  skipped")
                    skipped += 1
                    continue
                payload = {
                    "kind": "merge_authors",
                    "keep": keep,
                    "drop": drop,
                    "note": f"converted claim_paper doi:{canonical_doi(doi)}",
                }
                subject_hash = merge_subject_hash(keep, drop)
                existing = con.execute(
                    "SELECT event_id FROM ledger_events WHERE orcid = ? AND kind = 'merge_authors' "
                    "AND subject_hash = ? AND revoked_at IS NULL",
                    (orcid, subject_hash),
                ).fetchone()
                if existing:
                    print(f"  already present (event {existing[0]})")
                    continue
                con.execute(
                    "INSERT INTO ledger_events "
                    "(orcid, kind, payload, subject_hash, moderation, moderated_by, moderated_at) "
                    "VALUES (?, 'merge_authors', ?, ?, 'accepted', ?, datetime('now'))",
                    (
                        orcid,
                        json.dumps(payload, separators=(",", ":")),
                        subject_hash,
                        f"convert:{admin_orcid}",
                    ),
                )
                con.commit()
                inserted += 1
                print("  inserted (accepted)")
    finally:
        con.close()
    print(f"\n{inserted} merge event(s) inserted, {skipped} skipped")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--measure", type=Path, required=True, help="claims-measure JSON path"
    )
    p.add_argument("--admin-orcid", required=True, help="admin ORCID for moderated_by")
    p.add_argument("--db", default=paths.DB_REL, help="SQLite DB path")
    args = p.parse_args()
    convert(args.measure, args.db, args.admin_orcid)


if __name__ == "__main__":
    main()
