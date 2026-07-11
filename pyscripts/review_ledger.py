"""AI review lane for pending user-ledger events (v1: claim_paper only).

For each pending claim without a verdict for the chosen model, builds a
deterministic evidence bundle from the `subject_enrichment` cache (written
exclusively by the SvelteKit server — run "Fetch metadata" on /admin/ledger
first) and runs one agentic session per claimant batch through the pluggable
engine registry (pyscripts/explore/runner.py) with the rankless MCP tools
attached. Structured verdicts land in `review_verdicts`, which the review
queue at /admin/ledger displays; nothing is ever moderated automatically here.

    uv run -m pyscripts review-ledger [--dry-run] [--model sonnet] [--limit N]

Cross-language type boundary (Python ↔ TS): rows written here mirror
`review_verdicts` DDL and the ReviewVerdict / WorkRecord / OrcidRecord types in
src/lib/types/review.ts; the DDL below mirrors src/lib/server/db.ts.
"""

import argparse
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pyscripts import paths
from pyscripts.explore import cli, runner

VERDICTS = ("approve", "reject", "unsure")
WORK_SOURCES = ("crossref", "openalex")
USABLE_STATUS = ("ok", "not_found")  # a missing record is itself evidence
LOG_DIR = Path("logs/review-ledger")
MAX_TURNS = 40

# Mirror of the review_verdicts DDL in src/lib/server/db.ts (kept in both places
# so whichever side touches a fresh DB first creates the same schema).
_SCHEMA = """
CREATE TABLE IF NOT EXISTS review_verdicts (
    verdict_id INTEGER PRIMARY KEY AUTOINCREMENT,
    orcid TEXT NOT NULL,
    kind TEXT NOT NULL,
    subject_hash TEXT NOT NULL,
    model TEXT NOT NULL,
    verdict TEXT NOT NULL,
    confidence REAL NOT NULL,
    reasoning TEXT NOT NULL,
    checks TEXT,
    created_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_rv_dedup
    ON review_verdicts(orcid, kind, subject_hash, model, created_at);
CREATE INDEX IF NOT EXISTS idx_rv_subject ON review_verdicts(orcid, kind, subject_hash);
"""

_SYSTEM = """You are the moderation reviewer for Rankless, a scholarly impact explorer.
An ORCID-authenticated user (the claimant) asserts authorship of papers via DOI.
Decide per claim: approve, reject, or unsure. Conclusive cases (claimant ORCID
present in the paper's Crossref/OpenAlex authorship record) are auto-approved
upstream and never reach you — you judge name matches and context.

The user message is a JSON evidence bundle for ONE claimant:
- claimant: ORCID, name from their ORCID record, their self-asserted works
  (count + title sample). null name = no public ORCID record.
- claims[]: id, doi, plucked crossref/openalex records (title, year, venue,
  authors with any ORCIDs). A null record means that source has no entry for
  the DOI — common for very fresh papers, not suspicious by itself.
- doi_on_orcid_record: the claimant lists this DOI on their own ORCID profile
  (self-asserted — supporting, never conclusive).

You have rankless MCP tools: probe the claimant's profile (lookup by ORCID),
their subfields, venues, and coauthor network, and search for the claimed
paper's coauthors. Use them for every non-obvious claim. No web access.

Verdict rules:
- approve: claimant's name is on the author list (accept initials, diacritics,
  transliteration, name-order variants) AND at least one corroborating signal
  (DOI on their ORCID record, field/venue consistency with their profile,
  coauthor overlap with their network).
- reject: the author list is present and clearly excludes the claimant AND the
  paper's field is unrelated to their profile (guard against citation boosting).
- unsure: no author metadata anywhere, ambiguous homonym, or conflicting signals.
Calibration: confidence >= 0.9 needs a name match plus corroboration; a bare
doi_on_orcid_record with no other record caps at unsure / 0.6.

Return ONLY this JSON object, no fences, no prose around it:
{"verdicts": [{"id": "<claim id>",
  "verdict": "approve" | "reject" | "unsure",
  "confidence": 0.0-1.0,
  "reasoning": "2-4 plain sentences an admin reads before clicking",
  "checks": {"name_on_author_list": "exact" | "variant" | "initials" | "absent" | "unknown",
             "field_consistency": "consistent" | "adjacent" | "unrelated" | "unknown",
             "coauthor_overlap": ["coauthor names also seen in the claimant's network"],
             "notes": "optional"}}]}
One verdict per claim id, every id exactly once."""


@dataclass
class Claim:
    event_id: int
    orcid: str
    kind: str
    subject_hash: str
    doi: str


@dataclass
class BatchResult:
    claims: list[Claim]
    verdicts: list[dict]
    error: str | None = None


def normalize_orcid(s: str) -> str:
    return re.sub(r"^https?://(www\.)?orcid\.org/", "", s.strip(), flags=re.I).upper()


def canonical_doi(doi: str) -> str:
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.strip(), flags=re.I).lower()


def connect(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout = 5000")
    con.executescript(_SCHEMA)
    return con


def select_claims(
    con: sqlite3.Connection, model: str, kind: str, limit: int | None, force: bool
) -> list[Claim]:
    if kind != "claim_paper":
        raise SystemExit(
            f"unsupported kind {kind!r}: the review lane handles claim_paper only"
        )
    rows = con.execute(
        """
        SELECT event_id, orcid, kind, subject_hash, payload FROM ledger_events
        WHERE moderation = 'pending_review' AND revoked_at IS NULL AND kind = ?
          AND (? OR NOT EXISTS (
            SELECT 1 FROM review_verdicts rv
            WHERE rv.orcid = ledger_events.orcid AND rv.kind = ledger_events.kind
              AND rv.subject_hash = ledger_events.subject_hash AND rv.model = ?))
        ORDER BY orcid, event_id
        """,
        (kind, int(force), model),
    ).fetchall()
    claims = []
    for r in rows:
        doi = (json.loads(r["payload"]).get("work") or {}).get("doi")
        if not doi:
            print(f"[review] skipping event {r['event_id']}: claim has no DOI")
            continue
        claims.append(
            Claim(
                r["event_id"],
                r["orcid"],
                r["kind"],
                r["subject_hash"],
                canonical_doi(doi),
            )
        )
    return claims[:limit] if limit else claims


def load_enrichment(
    con: sqlite3.Connection, claims: list[Claim]
) -> dict[tuple[str, str], dict]:
    """Evidence per (source, key); SystemExit listing every missing pair."""
    needed = {("orcid", normalize_orcid(c.orcid)) for c in claims}
    for c in claims:
        needed.update((src, c.doi) for src in WORK_SOURCES)
    found: dict[tuple[str, str], dict] = {}
    missing = []
    for source, key in sorted(needed):
        row = con.execute(
            "SELECT status, data FROM subject_enrichment WHERE source = ? AND key = ?",
            (source, key),
        ).fetchone()
        if row is None or row["status"] not in USABLE_STATUS:
            missing.append(f"  ({source}, {key})")
        else:
            found[(source, key)] = {
                "status": row["status"],
                "data": json.loads(row["data"]) if row["data"] else None,
            }
    if missing:
        raise SystemExit(
            "enrichment missing for:\n"
            + "\n".join(missing)
            + "\nrun 'Fetch metadata' on /admin/ledger (or POST /api/admin/enrich) first —"
            " enrichment fetching lives in the SvelteKit server only."
        )
    return found


def build_bundle(claims: list[Claim], evidence: dict[tuple[str, str], dict]) -> dict:
    orcid = normalize_orcid(claims[0].orcid)
    record = evidence[("orcid", orcid)]["data"] or {}
    return {
        "claimant": {
            "orcid": orcid,
            "orcid_name": record.get("name"),
            "orcid_works_count": record.get("n_works", 0),
            "orcid_work_titles_sample": record.get("work_titles", [])[:20],
        },
        "claims": [
            {
                "id": str(c.event_id),
                "doi": c.doi,
                "crossref": evidence[("crossref", c.doi)]["data"],
                "openalex": evidence[("openalex", c.doi)]["data"],
                "doi_on_orcid_record": c.doi in set(record.get("work_dois", [])),
            }
            for c in claims
        ],
    }


def validate_verdicts(obj: object, claims: list[Claim]) -> list[dict]:
    verdicts = obj.get("verdicts") if isinstance(obj, dict) else None
    if not isinstance(verdicts, list):
        raise ValueError("response has no 'verdicts' list")
    expected = {str(c.event_id) for c in claims}
    seen = {}
    for v in verdicts:
        vid = str(v.get("id"))
        if vid not in expected:
            raise ValueError(f"unexpected claim id {vid!r}")
        if vid in seen:
            raise ValueError(f"duplicate claim id {vid!r}")
        if v.get("verdict") not in VERDICTS:
            raise ValueError(
                f"claim {vid}: verdict {v.get('verdict')!r} not in {VERDICTS}"
            )
        conf = v.get("confidence")
        if not isinstance(conf, (int, float)) or not 0 <= conf <= 1:
            raise ValueError(f"claim {vid}: confidence {conf!r} not in [0, 1]")
        if not isinstance(v.get("reasoning"), str) or not v["reasoning"].strip():
            raise ValueError(f"claim {vid}: empty reasoning")
        seen[vid] = v
    if extra := expected - set(seen):
        raise ValueError(f"missing verdicts for claim ids {sorted(extra)}")
    return [seen[str(c.event_id)] for c in claims]


def insert_verdicts(
    con: sqlite3.Connection,
    result: BatchResult,
    evidence: dict[tuple[str, str], dict],
    model: str,
    stamp: str,
) -> None:
    for claim, verdict in zip(result.claims, result.verdicts):
        checks = dict(verdict.get("checks") or {})
        checks["crossref_status"] = evidence[("crossref", claim.doi)]["status"]
        checks["openalex_status"] = evidence[("openalex", claim.doi)]["status"]
        con.execute(
            """
            INSERT OR IGNORE INTO review_verdicts
                (orcid, kind, subject_hash, model, verdict, confidence, reasoning, checks, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                claim.orcid,
                claim.kind,
                claim.subject_hash,
                model,
                verdict["verdict"],
                float(verdict["confidence"]),
                verdict["reasoning"].strip(),
                json.dumps(checks),
                stamp,
            ),
        )
    con.commit()


def run_batch(
    claims: list[Claim],
    evidence: dict[tuple[str, str], dict],
    args: argparse.Namespace,
    backend_url: str,
) -> BatchResult:
    bundle = build_bundle(claims, evidence)
    job = runner.MineJob(
        system=_SYSTEM,
        user=json.dumps(bundle, ensure_ascii=False, indent=1),
        model=cli.resolve_model(args.model),
        backend_url=backend_url,
        max_turns=MAX_TURNS,
        timeout_s=args.timeout_s,
    )
    orcid = normalize_orcid(claims[0].orcid)
    try:
        raw = runner.get_runner(args.runner)(job)
        return BatchResult(claims, validate_verdicts(cli.parse_json(raw), claims))
    except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        log = LOG_DIR / f"{stamp}-{orcid}.txt"
        log.write_text(f"{exc}\n\n{locals().get('raw', '<no response>')}")
        return BatchResult(claims, [], error=f"{exc} (raw response: {log})")


def batches(claims: list[Claim], size: int) -> list[list[Claim]]:
    by_orcid: dict[str, list[Claim]] = {}
    for c in claims:
        by_orcid.setdefault(c.orcid, []).append(c)
    return [
        group[i : i + size]
        for group in by_orcid.values()
        for i in range(0, len(group), size)
    ]


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db", default=paths.DB_REL, help=f"sqlite path (default {paths.DB_REL})"
    )
    parser.add_argument(
        "--model", default=cli.DEFAULT_MODEL, help="model name or alias"
    )
    parser.add_argument(
        "--runner", default=runner.DEFAULT_RUNNER, help="engine registry key"
    )
    parser.add_argument(
        "--backend",
        default="local",
        help=f"one of {list(runner.BACKENDS)} or a full /v1 base URL (default: local).",
    )
    parser.add_argument(
        "--kind", default="claim_paper", help="event kind (v1: claim_paper only)"
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="cap the number of claims"
    )
    parser.add_argument(
        "--batch-size", type=int, default=8, help="max claims per agent session"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-review claims that already have a verdict",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print selection + prompts, call nothing"
    )
    parser.add_argument(
        "--timeout-s", type=int, default=900, help="per-session hard timeout"
    )


def run(args: argparse.Namespace) -> None:
    backend_url, backend_label = runner.resolve_backend(args.backend)
    con = connect(args.db)
    claims = select_claims(con, args.model, args.kind, args.limit, args.force)
    if not claims:
        print("[review] nothing to review (no pending claims without a verdict).")
        return
    evidence = load_enrichment(con, claims)
    groups = batches(claims, args.batch_size)
    print(
        f"[review] {len(claims)} claim(s) from {len({c.orcid for c in claims})} claimant(s)"
        f" in {len(groups)} batch(es); model={args.model} backend={backend_label}"
    )

    if args.dry_run:
        for group in groups:
            bundle = build_bundle(group, evidence)
            print(f"\n--- batch: {bundle['claimant']['orcid']} ---")
            print(json.dumps(bundle, ensure_ascii=False, indent=1))
        return

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    failures = []
    counts = dict.fromkeys(VERDICTS, 0)
    for group in groups:
        result = run_batch(group, evidence, args, backend_url)
        if result.error:
            failures.append(result.error)
            print(
                f"[review] FAILED batch {normalize_orcid(group[0].orcid)}: {result.error}"
            )
            continue
        insert_verdicts(con, result, evidence, args.model, stamp)
        for claim, verdict in zip(result.claims, result.verdicts):
            counts[verdict["verdict"]] += 1
            print(
                f"[review] #{claim.event_id} {claim.doi}: {verdict['verdict']}"
                f" ({verdict['confidence']:.2f}) — {verdict['reasoning']}"
            )
    print(f"[review] done: {counts}, {len(failures)} failed batch(es)")
    if failures:
        raise SystemExit(1)
