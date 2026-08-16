"""Paper-claim release lane: review, apply, accept, record (`uv run -m pyscripts claims <step>`).

A release's claim decisions are *data*, not code: everything case-specific lives in a
per-release plan file (the driver keeps it beside its other release notes, never in the
repo), and every step here is a pure reader/writer of it.

    {
      "measured_against": "snapshot 2026-06-30 entity-csvs",   # provenance, free text
      "generated_for_run": "claims release 2026-08-15",
      "claims": [
        {
          "orcid": "0000-…", "name": "…", "doi": "10.…",      # the submitted claim
          "verdict": "direct" | "merge" | "unreachable",       # from measurement
          "reason": "" | "oa_id_not_in_dataset" | "doi_not_in_snapshot" | "orcid_not_in_dataset",
          "work": "W…", "keep": "A…",                          # claimed work, claimant's record
          "work_authors": ["A…"],                              # author records on the work
          "merge_candidates": ["A…"],                          # merge verdicts: name-matched records
          "merge": {"drop": "A…", "decision": "approved" | "rejected",
                    "note": "…", "decided_by": "0000-…"}       # written by review-merges
        }
      ]
    }

`verdict`/`reason`/`merge_candidates` come from measuring the claims against the snapshot
CSVs the pipeline actually reads — the OpenAlex API attributes recent papers the snapshot
does not, and the pipeline believes the snapshot. That measurement is per-release analysis;
its output is the plan file.

The steps, in release order:

  review-merges  a claim whose DOI the snapshot credits to a name-matching *other* record
                 cannot be satisfied by the forced-oeuvre pass alone; an author merge is
                 the resolution. A wrong author merge is the highest-damage event the
                 ledger can write, so this asks y/n per candidate and records the verdict
                 (both ways, with the reason) back into the plan.
  apply-merges   writes the approved decisions as accepted `merge_authors` events.
  accept         accepts the claims the snapshot proves — the claimant's record is already
                 on the work, or an approved merge now credits them. Everything else stays
                 `pending_review`: accepting an unverified claim would silently auto-apply
                 the moment a future snapshot filled the gap.
  record         writes the release's claims sidecar (docs/deploy.md).
"""

import json
import os
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from protocli import Dispatcher

from pyscripts import paths
from pyscripts.ledger_ids import (
    author_subject,
    canonical_doi,
    merge_subject_hash,
    oa_numeric,
)

load_dotenv()
DEFAULT_PLAN = ".cril/claims-plan.json"
MODERATED_BY = "auto:snapshot-authorship"
WORK_SOURCES = ("openalex", "crossref")
# Plan verdict/reason → the cause named in the report. Public phrasing: no internal
# skip-reason identifiers, no individual named.
CAUSES = {
    "oa_id_not_in_dataset": "paper carries no author records to attribute",
    "doi_not_in_snapshot": "DOI absent from this snapshot",
    "orcid_not_in_dataset": "claimant has no author record in this snapshot",
    "identity_match_rejected": "only candidate match was a different researcher",
}


def review_merges(
    *,
    admin_orcid: str,
    plan: str = DEFAULT_PLAN,
    db: str = paths.DB_REL,
) -> None:
    """Decide each merge candidate y/n; decisions are written back into the plan."""
    plan_path = Path(plan)
    doc = json.loads(plan_path.read_text())
    con = _connect(db)
    try:
        for claim in doc["claims"]:
            if claim["verdict"] != "merge":
                continue
            decided = claim.get("merge")
            if decided:
                print(f"\n{_claim_line(claim)}\n  already {decided['decision']}")
                continue
            candidates = [
                c for c in claim.get("merge_candidates", []) if c != claim["keep"]
            ]
            if not candidates:
                print(
                    f"\n{_claim_line(claim)}\n  no merge candidate in the plan — the "
                    "measurement names the records that matched, add them as "
                    "`merge_candidates` or leave the claim unresolved"
                )
                continue
            print(f"\n{_claim_line(claim)}")
            print(
                f"  claimant: {claim['name']} keeps https://openalex.org/{claim['keep']}"
            )
            print(_work_evidence(con, claim["doi"]))
            for drop in candidates:
                print(f"  drops:    https://openalex.org/{drop}")
                if input("  merge? [y/N] ").strip().lower() == "y":
                    claim["merge"] = _decision("approved", drop, admin_orcid)
                    break
            else:
                why = input("  none approved — why? ").strip()
                claim["merge"] = _decision("rejected", candidates[0], admin_orcid, why)
            print(f"  recorded: {claim['merge']['decision']}")
    finally:
        con.close()
    plan_path.write_text(json.dumps(doc, indent=1))
    print(f"\ndecisions written to {plan_path}")


def apply_merges(
    *,
    admin_orcid: str,
    plan: str = DEFAULT_PLAN,
    db: str = paths.DB_REL,
    dry_run: bool = False,
) -> None:
    """Write the approved merges as accepted `merge_authors` events (idempotent)."""
    doc = json.loads(Path(plan).read_text())
    con = _connect(db)
    inserted = existing = 0
    try:
        for claim in doc["claims"]:
            decision = claim.get("merge") or {}
            if decision.get("decision") != "approved":
                continue
            keep = author_subject(
                oa_numeric(claim["keep"]), claim["orcid"], claim["name"]
            )
            drop = author_subject(oa_numeric(decision["drop"]), None, "")
            subject_hash = merge_subject_hash(keep, drop)
            row = con.execute(
                "SELECT event_id FROM ledger_events WHERE orcid = ? AND kind = 'merge_authors' "
                "AND subject_hash = ? AND revoked_at IS NULL",
                (claim["orcid"], subject_hash),
            ).fetchone()
            if row:
                print(f"  {claim['name']:20s} {decision['drop']}  already present")
                existing += 1
                continue
            print(
                f"  {claim['name']:20s} {decision['drop']} -> {claim['keep']}  ({claim['doi']})"
            )
            inserted += 1
            if dry_run:
                continue
            payload = {
                "kind": "merge_authors",
                "keep": keep,
                "drop": drop,
                "note": f"converted claim_paper doi:{canonical_doi(claim['doi'])}",
            }
            con.execute(
                "INSERT INTO ledger_events "
                "(orcid, kind, payload, subject_hash, moderation, moderated_by, moderated_at) "
                "VALUES (?, 'merge_authors', ?, ?, 'accepted', ?, datetime('now'))",
                (
                    claim["orcid"],
                    json.dumps(payload, separators=(",", ":")),
                    subject_hash,
                    f"convert:{admin_orcid}",
                ),
            )
            con.commit()
    finally:
        con.close()
    verb = "would insert" if dry_run else "inserted"
    print(f"\n{verb} {inserted}, {existing} already present")
    for claim in doc["claims"]:
        decision = claim.get("merge") or {}
        if decision.get("decision") == "rejected":
            print(
                f"  rejected on review: {claim['name']:20s} {decision.get('note', '')}"
            )


def accept(
    *,
    plan: str = DEFAULT_PLAN,
    db: str = paths.DB_REL,
    dry_run: bool = False,
) -> int:
    """Accept the claims the snapshot proves; the rest stay pending_review."""
    doc = json.loads(Path(plan).read_text())
    con = _connect(db)
    con.row_factory = sqlite3.Row
    rows, drops = _claim_rows(con), _merged_drops(con)
    tally: Counter = Counter()
    to_accept, held = [], []

    for claim in doc["claims"]:
        row = rows.get((claim["orcid"].upper(), canonical_doi(claim["doi"])))
        if row is None:
            tally["no matching ledger row"] += 1
            held.append((claim, "not in the DB"))
        elif not _resolvable(claim, drops):
            reason = claim["reason"] or "merge not confirmed"
            tally[f"held pending ({reason})"] += 1
            held.append((claim, reason))
        elif row["moderation"] != "pending_review":
            tally[f"already {row['moderation']}"] += 1
        else:
            to_accept.append(row["event_id"])
            tally[f"accept ({claim['verdict']})"] += 1

    if not dry_run:
        con.executemany(
            "UPDATE ledger_events SET moderation = 'accepted', moderated_by = ?, "
            "moderated_at = datetime('now') "
            "WHERE event_id = ? AND moderation = 'pending_review'",
            [(MODERATED_BY, eid) for eid in to_accept],
        )
        con.commit()

    total = con.execute(
        "SELECT count(*) FROM ledger_events WHERE kind = 'claim_paper' "
        "AND revoked_at IS NULL AND moderation IN ('accepted', 'auto_ok')"
    ).fetchone()[0]
    con.close()

    print(f"{'DRY RUN — ' if dry_run else ''}claim acceptance")
    for k, v in sorted(tally.items()):
        print(f"  {v:3d}  {k}")
    if held:
        print("\n  held pending (no snapshot evidence):")
        for claim, why in held:
            print(f"    {claim['name']:22s} {claim['doi']:34s} {why}")
    print(f"\naccepted claim_paper events in the ledger: {total}")
    print("`applied.claim_paper` should match this after refresh-data")
    return total


def record(
    *,
    plan: str = DEFAULT_PLAN,
    db: str = paths.DB_REL,
    root: str | None = None,
) -> Path:
    """Write `$OA_ROOT/releases/<run_id>.claims.json` — what every claim did, and why.

    `applied_manifest.json` records what the pipeline integrated, but a claim that was
    never accepted is never exported, so it leaves no trace at all: the release record
    would show the claims that landed and stay silent about the ones that could not.
    Publishable aggregates at the top level (`recalc manifest` folds them in as
    `claims_review`); per-claim detail under `detail`, which never leaves the box.
    `releases/` is push- and digest-excluded, so writing it after the stamp is safe.
    """
    root_path = Path(root or os.environ["OA_ROOT"])
    built = build_record(json.loads(Path(plan).read_text()), root_path, db)
    rdir = root_path / "releases"
    rdir.mkdir(exist_ok=True)
    out = rdir / f"{built['run_id']}.claims.json"
    out.write_text(json.dumps(built, indent=1))

    print(f"claims record: {built['applied']}/{built['submitted']} claims applied")
    for cause, n in built["unresolved_by_cause"].items():
        print(f"  {n:3d}  {cause}")
    print(
        f"  author merges: {built['merges_approved']} of {built['merges_reviewed']} "
        "reviewed candidates approved"
    )
    print(f"written to {out} (detail stays on this box)")
    return out


def build_record(doc: dict, root: Path, db_path: str) -> dict:
    ul = root / "user-ledger"
    applied_keys = set(
        json.loads((ul / "applied_manifest.json").read_text())["applied_keys"]
    )
    run_id = json.loads((ul / "snapshot_manifest.json").read_text())["run_id"]
    con = _connect(db_path)
    con.row_factory = sqlite3.Row
    keys = _claim_keys(con)
    con.close()

    detail, causes = [], Counter()
    for claim in doc["claims"]:
        key = keys.get((claim["orcid"].upper(), canonical_doi(claim["doi"])))
        landed = key is not None and key in applied_keys
        decision = claim.get("merge") or {}
        if landed:
            cause = None
        elif decision.get("decision") == "rejected":
            cause = CAUSES["identity_match_rejected"]
        else:
            cause = CAUSES.get(claim["reason"], claim["reason"] or "unresolved")
        if cause:
            causes[cause] += 1
        detail.append(
            {
                "name": claim["name"],
                "orcid": claim["orcid"],
                "doi": claim["doi"],
                "applied": landed,
                "cause": cause,
            }
        )

    decisions = [c.get("merge") for c in doc["claims"] if c.get("merge")]
    applied = sum(1 for d in detail if d["applied"])
    return {
        "run_id": run_id,
        "submitted": len(detail),
        "applied": applied,
        "unresolved": len(detail) - applied,
        "unresolved_by_cause": dict(causes.most_common()),
        "merges_reviewed": len(decisions),
        "merges_approved": sum(1 for d in decisions if d["decision"] == "approved"),
        "detail": detail,
    }


_dispatcher = Dispatcher(
    "pyscripts claims",
    {
        "review-merges": review_merges,
        "apply-merges": apply_merges,
        "accept": accept,
        "record": record,
    },
)


def _connect(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA busy_timeout = 30000")
    return con


def _decision(
    decision: str, drop: str, admin_orcid: str, note: str = ""
) -> dict[str, Any]:
    return {
        "drop": drop,
        "decision": decision,
        "note": note,
        "decided_by": admin_orcid,
    }


def _claim_line(claim: dict) -> str:
    return f"claim {claim['orcid']} → {claim['doi']} ({claim['name']})"


def _work_evidence(con: sqlite3.Connection, doi: str) -> str:
    for source in WORK_SOURCES:
        row = con.execute(
            "SELECT data FROM subject_enrichment WHERE source = ? AND key = ? AND status = 'ok'",
            (source, canonical_doi(doi)),
        ).fetchone()
        if row and row[0]:
            rec = json.loads(row[0])
            authors = ", ".join(a["name"] for a in rec.get("authors") or [])
            return f"  title:   {rec.get('title')} ({rec.get('year')}, {source})\n  authors: {authors}"
    return "  (no enrichment cached — run 'Fetch metadata' on /admin/ledger for the title/author list)"


def _claim_rows(con: sqlite3.Connection) -> dict[tuple[str, str], sqlite3.Row]:
    """(orcid, canonical doi) -> row, for every live claim_paper event."""
    out = {}
    for row in con.execute(
        "SELECT event_id, orcid, payload, moderation FROM ledger_events "
        "WHERE kind = 'claim_paper' AND revoked_at IS NULL"
    ):
        doi = (json.loads(row["payload"]).get("work") or {}).get("doi")
        if doi:
            out[(row["orcid"].upper(), canonical_doi(doi))] = row
    return out


def _claim_keys(con: sqlite3.Connection) -> dict[tuple[str, str], str]:
    """(orcid, canonical doi) -> the ledger key applied_manifest refers to."""
    out = {}
    for row in con.execute(
        "SELECT orcid, payload, subject_hash FROM ledger_events "
        "WHERE kind = 'claim_paper' AND revoked_at IS NULL"
    ):
        doi = (json.loads(row["payload"]).get("work") or {}).get("doi")
        if doi:
            key = f"{row['orcid']}|claim_paper|{row['subject_hash']}"
            out[(row["orcid"].upper(), canonical_doi(doi))] = key
    return out


def _merged_drops(con: sqlite3.Connection) -> dict[str, set[int]]:
    """orcid -> author oa_ids an accepted merge_authors event folds into them."""
    out: dict[str, set[int]] = {}
    for row in con.execute(
        "SELECT orcid, payload FROM ledger_events WHERE kind = 'merge_authors' "
        "AND revoked_at IS NULL AND moderation IN ('accepted', 'auto_ok')"
    ):
        drop = (json.loads(row["payload"]).get("drop") or {}).get("oa_id")
        if drop is not None:
            out.setdefault(row["orcid"].upper(), set()).add(int(drop))
    return out


def _resolvable(claim: dict, drops: dict[str, set[int]]) -> bool:
    if claim["verdict"] == "direct":
        return True
    if claim["verdict"] != "merge":
        return False
    have = drops.get(claim["orcid"].upper(), set())
    return any(oa_numeric(a) in have for a in claim["work_authors"])
