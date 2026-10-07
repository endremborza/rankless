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
A claim from the site forces nothing on its own: every signed-in owner's whole œuvre already rides through the type/citation screens, so a site claim is a status line, and it never adds an authorship row. A claim names its paper by DOI, which stands for every work record carrying it, or by the record the claimant saw when it has no DOI or the snapshot has the DOI on no record. It applies where the snapshot credits the claimant on one of those records once merges, disowns and reassignments are applied. A paper the snapshot lists under another record of the person (e.g. an unmerged one without the ORCID) needs that record merged: the merge carries the row, with its affiliations, onto the person. A curated `claim_paper` line (`curated.jsonl`) is forced: where the snapshot credits the claimant on no record of the paper, it grants them a row on the most cited one, after the listed rows and without an affiliation, and the record they are credited on rides through the type/citation screens like an owner's œuvre. A forced claim on a paper an unmerged record of the person is already on lists them twice, so the curated batch merges such records first. Skips: `doi_not_in_snapshot`, `oa_id_not_in_dataset`, `orcid_not_in_dataset`, `claimant_not_attributed`, and `work_screened` for a claim credited only on records the type or citation screen drops.

The other skip reasons the applied manifest carries: `author_not_on_work` (a disown or a reassignment whose row is not there, e.g. the paper sits on an unmerged record of the person), `superseded` (a later event decides the same record or row) and `merge_cycle` (the keep already merges into the drop).

## Release claims lane (`pyscripts/claims.py`)

`uv run -m pyscripts claims <step>` is the driver-side counterpart of the queue,
for the batch of claims a release resolves. It exists because the queue's hard
evidence is the **OpenAlex API**, while the pipeline reads the **snapshot** — the
two disagree on recent papers, and a claim the snapshot credits to another record of
the same person applies only once that record is merged.

Everything case-specific is data: a per-release plan file (one entry per
submitted claim — verdict, reason, the claimant's author record, the work's
author records, the name-matched merge candidates) that measurement against the
snapshot CSVs produces. It lives with the driver's release notes, never in the
repo, and the steps only read and write it:

- `review-merges` — a claim whose DOI the snapshot credits to a name-matching
  _other_ record needs an author merge. y/n per candidate, with the cached work
  metadata as evidence; the verdict — approved _or_ rejected, with its reason —
  is written back into the plan, so the decision is recorded rather than
  re-litigated.
- `apply-merges` — writes the approved ones as accepted `merge_authors` events
  (actor = claimant, `moderated_by = convert:<admin>`), idempotent.
- `accept` — accepts the claims the snapshot proves (claimant already on the
  work, or credited via an approved merge), `moderated_by =
'auto:snapshot-authorship'` — an automated tier in the queue like
  `auto:doi-authorship`. Everything else stays `pending_review`.
- `record` — the release's claims sidecar, [deploy.md](deploy.md).

Live's DB keeps its own copies as `pending_review`; the reconcile never reverts
a decided row, so `merge_db_to_live` carries the decisions across whenever
convenient.

## Enrichment cache (`subject_enrichment`)

Claim payloads are often DOI-only (fresh papers missing from the OA snapshot),
so display and evidence both come from external records, cached in SQLite:

| source | key | data (see `src/lib/types/review.ts`) |
| --- | --- | --- |
| `crossref` | canonical DOI | `WorkRecord` — title/year/venue + authors w/ asserted ORCIDs |
| `openalex` | canonical DOI | `WorkRecord` — same + `oa_work_id` |
| `orcid` | bare ORCID | `OrcidRecord` — name + self-asserted work DOIs/titles |

The **only fetcher is the SvelteKit server** (`src/lib/server/enrich.ts`,
orchestrated by `review-data.ts`): the "Fetch metadata" button on
`/admin/ledger` loops `POST /api/admin/enrich`, which fetches a bounded chunk
(`DEFAULT_LIMIT` in `src/routes/api/admin/enrich/+server.ts`) per call, upserts the cache, and runs the hard-evidence pass.
`status` is `ok | not_found | error`; `not_found` is kept as evidence (no such
record), `error` rows are retried on the next run. Set `ENRICH_MAILTO` for
polite-pool headers. Python never fetches — the AI lane fails loudly listing
missing pairs and points at the button.

## AI lane (`pyscripts/review_ledger.py`)

```
uv run -m pyscripts review-ledger [--db PATH] [--model NAME]
    [--runner NAME] [--backend local|live|URL] [--limit N]
    [--batch-size N] [--force] [--dry-run] [--timeout-s N]
```

`--batch-size` and `--timeout-s` default to `DEFAULT_BATCH_SIZE` and `DEFAULT_TIMEOUT_S` in `pyscripts/review_ledger.py`.

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

`event_id` is renumbered by the `userdb.py` merge, so review data is keyed by
the stable subject identity **`(orcid, kind, subject_hash)`**. Both new tables
are in `userdb.TABLES` and ride the existing `merge_db_*` / `sync_db_*`
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

1. `make dev` (backend + frontend dev server); `ADMIN_ORCIDS=<your orcid>`.
2. `/dev-login`, create claims via `POST /api/ledger` (one DOI whose record
   carries your ORCID, a few foreign ones).
3. `/admin/ledger` → Fetch metadata → titles/links appear, the proven claim
   flips to accepted with the `auto` badge.
4. `uv run -m pyscripts review-ledger --dry-run`, then with `--limit`;
   reload the queue for verdict badges; bulk-moderate the rest.
5. Tests: `bun run test:unit` (pluckers, hard evidence), `uv run pytest
pyscripts/tests/test_review_ledger.py` (selection, gate, validation, dedup).
