# Ledger review

How user-submitted ledger events (claim/disown/merge) get reviewed at scale: a
moderation queue at `/admin/ledger`, a deterministic hard-evidence tier that
auto-accepts proven claims, and an advisory AI lane for everything fuzzy.
Humans make every remaining decision; the AI never moderates.

## Review tiers

1. **Hard evidence (automatic).** A `claim_paper` is proven when the claimant's
   ORCID appears in the DOI's Crossref or OpenAlex authorship record
   (`evaluateDoiAuthorship`, `src/lib/server/review.ts`). Proven pending claims
   are accepted during enrichment with `moderated_by = 'auto:doi-authorship'`
   (the `auto:` prefix renders as a badge; the decision is a normal moderation
   row and can be audited like any other).
2. **AI verdicts (advisory).** `uv run -m pyscripts review-ledger` produces
   `approve | reject | unsure` + confidence + reasoning per remaining claim,
   shown as an expandable badge in the queue.
3. **Human click.** Approve/Reject per row or in bulk; `moderated_by` records
   which admin (multiple admins supported via `ADMIN_ORCIDS`).

Accepted events flow to the pipeline via `export_user_ledger.py` as before.
The filter step resolves each claim's DOI to a work and forces it through the
type/citation screens; a claim is applied when the claimant is credited on the
surviving work (skips: `doi_not_in_snapshot`, `orcid_not_in_dataset`,
`oa_id_not_in_dataset`, `claimant_not_attributed`).

## Enrichment cache (`subject_enrichment`)

Claim payloads are often DOI-only (fresh papers missing from the OA snapshot),
so display and evidence both come from external records, cached in SQLite:

| source     | key           | data (see `src/lib/types/review.ts`)                         |
| ---------- | ------------- | ------------------------------------------------------------ |
| `crossref` | canonical DOI | `WorkRecord` — title/year/venue + authors w/ asserted ORCIDs |
| `openalex` | canonical DOI | `WorkRecord` — same + `oa_work_id`                           |
| `orcid`    | bare ORCID    | `OrcidRecord` — name + self-asserted work DOIs/titles        |

The **only fetcher is the SvelteKit server** (`src/lib/server/enrich.ts`,
orchestrated by `review-data.ts`): the "Fetch metadata" button on
`/admin/ledger` loops `POST /api/admin/enrich`, which fetches a bounded chunk
(default 40) per call, upserts the cache, and runs the hard-evidence pass.
`status` is `ok | not_found | error`; `not_found` is kept as evidence (no such
record), `error` rows are retried on the next run. Set `ENRICH_MAILTO` for
polite-pool headers. Python never fetches — the AI lane fails loudly listing
missing pairs and points at the button.

## AI lane (`pyscripts/review_ledger.py`)

```
uv run -m pyscripts review-ledger [--db data/rankless.sqlite] [--model sonnet]
    [--runner claude-cli] [--backend local|live|URL] [--limit N]
    [--batch-size 8] [--force] [--dry-run] [--timeout-s 900]
```

Selects pending, non-revoked `claim_paper` events lacking a verdict for the
chosen model, groups them per claimant (shared ORCID evidence, cross-claim
consistency), and runs one agentic session per batch through the engine
registry (`pyscripts/explore/runner.py`) with the rankless MCP tools attached —
the agent probes the claimant's profile, subfields, and coauthor network, but
has no web access. The evidence bundle per claim: plucked Crossref/OpenAlex
records + `doi_on_orcid_record` (self-asserted). Responses are validated
(every claim id exactly once, enum verdict, confidence in [0,1], non-empty
reasoning); failed batches dump the raw response under `logs/review-ledger/`
and exit nonzero at the end.

## Queue UI (`/admin/ledger`)

URL-driven (shareable) filters: `state` (default `pending`), `kind`, `actor`,
`page`, `per`. Events are grouped per claimant with name (users table → ORCID
record fallback), orcid.org link, and internal author link when known; work
rows show enriched title/year/venue with doi.org/openalex.org anchors. Bulk or
per-row decisions post to `/api/admin/moderate` (`{event_ids[], decision}`,
one transaction) and patch rows locally — no full reload per click.

## Cross-box movement

`event_id` is renumbered by the `mcp_db.py` merge, so review data is keyed by
the stable subject identity **`(orcid, kind, subject_hash)`**. Both new tables
are in `mcp_db.TABLES` and ride the existing `merge_db_*` / `sync_db_*`
transport: `review_verdicts` is append-only with a deterministic dedup index
(writer-supplied `created_at`, so a double merge inserts nothing);
`subject_enrichment` has a natural PK (target's copy wins on merge).

Merge also reconciles `moderation` for `ledger_events` rows both boxes already
hold, matched by the same logical key: an incoming decision
(`accepted`/`rejected`/`auto_ok`) flips a target row still `pending_review`
(copying `moderated_by`/`moderated_at`); a decided target never reverts to
pending, and two conflicting decisions keep the target's with a warning. So
decisions made on the authoritative box (live) reach every box at its next
pull.

## Verifying end-to-end (dev box)

1. Backend on 3038 + frontend dev server; `ADMIN_ORCIDS=<your orcid>`.
2. `/dev-login`, create claims via `POST /api/ledger` (one DOI whose record
   carries your ORCID, a few foreign ones).
3. `/admin/ledger` → Fetch metadata → titles/links appear, the proven claim
   flips to accepted with the `auto` badge.
4. `uv run -m pyscripts review-ledger --dry-run`, then with `--limit`;
   reload the queue for verdict badges; bulk-moderate the rest.
5. Tests: `bun run test:unit` (pluckers, hard evidence), `uv run pytest
pyscripts/tests/test_review_ledger.py` (selection, gate, validation, dedup).
