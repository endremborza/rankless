# Author Profile Modification Ledger

> Persistent, user-authored modifications to author profiles (ORCID-authenticated)
> that flow into the pipeline at the earliest possible stage and cascade through
> every downstream artefact. This document is the architecture reference and
> work breakdown; agents/humans executing it should follow the phases in order
> and delete completed sections as they land (per the repo planning convention).

---

## 1. Problem statement

A logged-in ORCID owner on `/author-papers/<semantic-id>/` can today:

- **Disown** an OpenAlex work (it's not theirs),
- **Claim** an OpenAlex work by DOI (OpenAlex missed the ORCID binding),
- **Merge two works** (same paper indexed twice),
- **Request merge of two author profiles** (same person, two `Authors` entities).

The existing storage (`src/lib/server/db.ts` — `disowned_papers`, `claimed_papers`,
`paper_merges`, `author_merge_requests`) is a **display-layer patch**:

- The Svelte page filters `disownedWids` / `mergedPairs` out of `AllWorks.svelte`.
- The binary pipeline never sees any of it — counts, peers, coauthor networks,
  subfield citation arrays, hit-paper membership, KD-tree embeddings all
  continue to reflect un-edited OpenAlex data.

We need a **durable ledger** of these modifications that:

1. Survives pipeline re-runs (the data product is re-built from CSVs nightly / on demand).
2. Is **applied as early as possible** inside the pipeline so every downstream
   artefact reflects the edit (not just the author's own paper list).
3. Distinguishes, per user, between **already-applied** events (consumed by the
   last pipeline run) and **pending** events (queued for the next run).
4. Allows both sets to be edited; edits also become **pending** until the next run.
5. Is extensible: the same mechanism must accept **future user actions**
   (add-a-paper-that-isn't-in-OpenAlex, self-removal, affiliation correction, …).

---

## 2. Open questions — please resolve before execution

These drive significant branches in the design. Defaults are noted but the
user should confirm before implementation.

1. **Auto-apply vs. moderation.** Current code has `reviewed` flag on
   `author_merge_requests` (human gate). Disowns/claims/paper-merges are
   auto-applied in-session. Should the pipeline apply **every** ledger event
   automatically on the next run, or should a subset (author-merge,
   high-impact claims) require staff approval first?
   *Proposed default:* disown / paper-merge — auto; claim — auto; author-merge —
   requires a `moderation` field set to `accepted` before the pipeline consumes it.
2. **Claim authority check.** A claim by DOI effectively asserts "this paper
   is mine." Should Node validate that the DOI resolves to an existing work
   (via a backend call at POST time) and reject claims where the work already
   has a different ORCID on one of its authorships?
   *Proposed default:* reject at API time only if the work exists AND has a
   conflicting ORCID; otherwise accept as pending.
3. **Paper-merge authority.** Should we require the authenticated ORCID to be
   listed on at least one side of the merge (keep or drop)?
   *Proposed default:* yes, one-side authority.
4. **Self-disown of all papers.** If a user disowns every paper they author,
   they'd drop below `MIN_AUTHOR_WORK_COUNT` and be filtered out — losing the
   ability to log in to edit further. Should the pipeline pin logged-in
   ORCIDs into the keep-filter regardless?
   *Proposed default:* yes, pin any ORCID that has ever submitted a ledger
   event into the author filter (bypass `MIN_AUTHOR_WORK_COUNT`).
5. **Revoking an already-applied event.** UI lets the user "undo" a merge that
   is already baked into the binary. The data cannot change live. Do we
   display a banner "revocation queued — applies at next data refresh," or do
   we allow a *client-side* overlay that unhides the paper immediately
   (similar to how today's merge is only UI-local)?
   *Proposed default:* banner + queue. No client-side overlay for applied
   events; the page reflects the current binary plus pending additions only.
6. **Cross-owner conflicts.** What if ORCID A disowns work W, and ORCID B
   claims W, and both refer to the same work? Or both claim the same DOI?
   *Proposed default:* last-writer-wins for disjoint actions on the same
   work; surface as a "conflict" state on the admin view; the pipeline
   applies them in `event_id` order deterministically. Phase 2 adds explicit
   conflict resolution.
7. **Add-a-paper-request.** User explicitly deferred implementation, but we
   must ensure the event schema accommodates it without migration. See §5.2.
8. **Snapshot concurrency.** If a user POSTs a new event while the pipeline
   is running, do we lock writes or accept and defer to the run-after-next?
   *Proposed default:* accept writes freely; the snapshot is taken at
   pipeline start and later writes are simply "pending" after the run.

---

## 3. Scope

### 3.1 In scope (this plan)
- Unified append-only `ledger_events` table (SQLite, same DB as today).
- Snapshot export: SQLite → `$OA_ROOT/user_ledger/active.jsonl` before `filter`.
- Pipeline ingest module consumed by `filter.rs`, `a1_entity_mapping`, `a2_init_atts`.
- Post-run `applied_manifest.json` written alongside pipeline output.
- Server reads the manifest and exposes applied/pending status per event.
- Frontend: two editable panels on the author page (Applied / Pending), plus
  consolidation of today's scattered `AuthorOwnerTools` / `AllWorks` actions
  into a single ledger UI.

### 3.2 Out of scope (Phase 2+)
- Full add-a-paper-request implementation (schema allocation only — no
  CSV-injection pipeline, no moderation UI).
- Admin moderation dashboard.
- Conflict resolution UI.
- E-mail / notification to the user when a queued event lands.

---

## 4. Architecture overview

```
┌───────────────────────────────────────────────────────────────────────┐
│ Browser (AuthorLedgerPanel.svelte)                                    │
│   └─ POST /api/ledger/* ───────────────┐                              │
└────────────────────────────────────────┼──────────────────────────────┘
                                         ▼
┌───────────────────────────────────────────────────────────────────────┐
│ SvelteKit server                                                      │
│   ledger.ts  (append-only ops on ledger_events)                       │
│   +page.server.ts  (loads events, joins applied_manifest.json)        │
└───────────────────────────────────────────────────────────────────────┘
                                         ▼  (one shared SQLite file)
┌───────────────────────────────────────────────────────────────────────┐
│ data/rankless.sqlite                                                  │
│   ledger_events (append-only, soft-revoke)                            │
└───────────────────────────────────────────────────────────────────────┘
                                         ▲
                                         │  pre-run export
                                         │
┌───────────────────────────────────────────────────────────────────────┐
│ pyscripts/export_user_ledger.py                                       │
│   reads ledger_events → writes $OA_ROOT/user_ledger/{                 │
│     active.jsonl        (normalised events, one per line)             │
│     snapshot_manifest.json  (run_id, event_ids included)              │
│   }                                                                   │
└───────────────────────────────────────────────────────────────────────┘
                                         ▼
┌───────────────────────────────────────────────────────────────────────┐
│ rankless_rs pipeline                                                  │
│   common/user_ledger.rs  (load + resolve ORCID/DOI/wid → BigId)       │
│   filter.rs              — consult alias map, pin owners              │
│   a1_entity_mapping      — alias author + work BigIds before dm_id    │
│   a2_init_atts           — drop/inject authorships, merge attrs       │
│                                                                       │
│ at end of run: writes $OA_ROOT/user_ledger/applied_manifest.json      │
│   { run_id, applied_event_ids, skipped: [{event_id, reason}, …] }     │
└───────────────────────────────────────────────────────────────────────┘
                                         ▼
┌───────────────────────────────────────────────────────────────────────┐
│ rankless_server (on startup)                                          │
│   reads applied_manifest.json → exposes via /ledger-status endpoint   │
└───────────────────────────────────────────────────────────────────────┘
```

### 4.1 State transitions per ledger event

```
                 ┌──────────┐  export snapshot   ┌──────────┐
  POST /api/…    │ pending  │ ─────────────────▶ │ in-run   │
  ────────────▶  │          │ ◀───── revoke ──── │ (frozen) │
                 └──────────┘                    └──────────┘
                       │                              │
                       │                              │ pipeline commit
                       │  revoke (soft delete)        ▼
                       │                         ┌──────────┐
                       │                         │ applied  │
                       │                         │          │
                       │  revoke-applied         │          │
                       │  (counter-event)        │          │
                       ▼                         ▼
                 ┌──────────┐                ┌──────────────┐
                 │ revoked  │ ◀── counter ── │ applied +    │
                 │ (pending)│                │ counter_pend │
                 └──────────┘                └──────────────┘
```

- `pending` → user created an event; not yet in any run's snapshot.
- `in-run` → snapshot taken; pipeline executing.
- `applied` → pipeline consumed it; manifest lists its event_id.
- `revoked` → user cancelled while still pending (before snapshot). Soft delete.
- `counter_pending` → an applied event was "undone" in the UI; a new *counter*
  event is created which the next pipeline run will cancel. This is the
  mechanism that preserves the **immutable** applied history while letting the
  UI appear "editable."

---

## 5. Data model

### 5.1 `ledger_events` table (SQLite)

```sql
CREATE TABLE ledger_events (
  event_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  orcid          TEXT NOT NULL,
  kind           TEXT NOT NULL,
    -- 'disown_paper' | 'claim_paper' | 'merge_papers'
    -- 'merge_authors' | 'add_paper_request' (deferred)
    -- 'revoke'  (counter-event: payload.target_event_id = N)
  payload        TEXT NOT NULL,      -- JSON, schema depends on kind
  subject_hash   TEXT NOT NULL,      -- stable hash of (orcid, kind, payload-key-fields);
                                     -- used for dedup and revoke lookup
  created_at     TEXT NOT NULL DEFAULT (datetime('now')),
  revoked_at     TEXT,               -- soft-delete (only for still-pending events)
  moderation     TEXT NOT NULL       -- 'auto_ok' | 'pending_review' | 'accepted' | 'rejected'
                 DEFAULT 'auto_ok'
);
CREATE INDEX idx_le_orcid ON ledger_events(orcid);
CREATE INDEX idx_le_kind  ON ledger_events(kind);
CREATE UNIQUE INDEX idx_le_dedup
  ON ledger_events(orcid, kind, subject_hash)
  WHERE revoked_at IS NULL;
```

Why one table:

- A single audit log per user (`SELECT … WHERE orcid = ?`) is trivial.
- "Applied vs pending" is a **join** against `applied_manifest.json`, not an
  extra column that has to be kept in sync.
- New kinds = new `kind` string + payload schema; no migrations.

The four existing tables (`disowned_papers`, `claimed_papers`, `paper_merges`,
`author_merge_requests`) become derivable views. **Migration**: one-shot
script in `pyscripts/migrate_ledger.py` inserts existing rows into
`ledger_events` with `created_at` preserved and `moderation = 'auto_ok'`
(except author-merge-requests where `reviewed = 0 → 'pending_review'`).
Then drop the old tables. This must happen **before** the Node rewrite goes
live.

### 5.2 Payload schemas (JSON)

```jsonc
// disown_paper
{ "wid": 12345 }

// claim_paper
{ "doi": "10.1234/foo.bar" }

// merge_papers
{ "wid_keep": 111, "wid_drop": 222 }

// merge_authors  (owner is always the "keep" side)
{ "my_semantic_id": "john-doe", "other_semantic_id": "j-doe-7", "note": "…" }

// add_paper_request  (deferred — schema reserved)
{ "doi": "...", "title": "...", "year": 2024, "coauthors": [...] }

// revoke  (counter-event)
{ "target_event_id": 12345, "reason": "..." }
```

`subject_hash` construction (stable, used for dedup):

- `disown_paper`: `sha1("disown_paper|<orcid>|<wid>")`
- `claim_paper`: `sha1("claim_paper|<orcid>|<normalized_doi>")`
- `merge_papers`: `sha1("merge_papers|<orcid>|<min(keep,drop)>|<max(keep,drop)>")`
- `merge_authors`: `sha1("merge_authors|<orcid>|<lexmin>|<lexmax>")`
- `revoke`: `sha1("revoke|<orcid>|<target_event_id>")`

### 5.3 Applied manifest

`$OA_ROOT/user_ledger/applied_manifest.json`:

```jsonc
{
  "run_id": "2026-04-22T10:00:00Z",          // ISO timestamp, generated by export step
  "snapshot_at": "2026-04-22T09:58:12Z",     // when active.jsonl was frozen
  "applied_event_ids": [42, 43, 47, 50, 51],
  "skipped": [
    { "event_id": 48, "reason": "orcid_not_in_dataset" },
    { "event_id": 49, "reason": "doi_not_found" }
  ]
}
```

Guarantees:

- An event is "applied" iff its `event_id ∈ applied_event_ids`.
- An event is "pending" iff it exists in `ledger_events` with
  `revoked_at IS NULL` and its `event_id` is NOT in the manifest.
- An event is "skipped" (orphan) if the pipeline rejected it — UI shows a
  specific error and lets the user edit or cancel.

---

## 6. Pipeline integration

### 6.1 Invariants the ledger must preserve

- `a1_entity_mapping`: the ID-mapping step. Any merge of two entities must
  collapse to a single `dm_id` **here**, so every subsequent step naturally
  sees the merge.
- `a2_init_atts::add_ship_relations`: the authorship rows are written here.
  Disowns and claims (injections) must happen **here**.
- `filter.rs`: runs before `a1`. Author survival thresholds
  (`MIN_AUTHOR_WORK_COUNT`, `MIN_AUTHOR_CITE_COUNT`) must account for author
  aliases (merged authors' works sum together) and must pin owners.

### 6.2 New module: `rankless_rs/src/common/user_ledger.rs`

```rust
pub struct UserLedger {
    pub run_id: String,
    pub orcid_to_owner_oa_id: HashMap<OrcidBytes, BigId>,
    pub author_aliases: HashMap<BigId, BigId>,     // drop_oa_id -> keep_oa_id
    pub work_aliases:   HashMap<BigId, BigId>,     // drop_oa_id -> keep_oa_id
    pub removed_edges:  HashSet<(BigId, BigId)>,   // (author_oa_id, work_oa_id)
    pub added_edges:    Vec<(BigId, BigId)>,       // (author_oa_id, work_oa_id)
    pub owner_pins:     HashSet<BigId>,            // author_oa_ids to never filter out
    pub applied:        Vec<u64>,                  // event_ids consumed
    pub skipped:        Vec<(u64, SkipReason)>,
}

impl UserLedger {
    pub fn load(stowage: &Stowage) -> Self;     // reads active.jsonl + snapshot_manifest
    pub fn resolve(&mut self, stowage: &Stowage);  // fill orcid→oa_id, doi→oa_id
    pub fn write_manifest(&self, stowage: &Stowage);  // applied_manifest.json
}
```

Resolution notes:

- ORCID → author oa_id: stream `authors/main` CSV once, build lookup.
- DOI → work oa_id: stream `works/main` CSV once, build `doi_to_oa_id`.
- Both passes are one-time per run and cached in memory.

### 6.3 Integration points

| Step | Change |
|------|--------|
| `filter.rs` (before a1) | Load `UserLedger`. In `count_passes`, collapse `author_aliases` groups before the threshold check. Force `owner_pins` authors to pass the filter. Remove edges in `removed_edges` from the counted `author→work` relation; add edges in `added_edges`. |
| `a1_entity_mapping.rs` | Inject a `BigIdRemapper` layer wrapping `Data64MappedEntityBuilder` usage for `Authors` and `Works`. When `push(oa_id)` is called with a `drop` side of an alias, skip (do not assign a dm_id); always re-route lookups through the alias map so downstream `LoadedIdMap` queries return the keep's dm_id. |
| `a2_init_atts::add_ship_relations::proc_next` | At the start of the fn, check `(author_oa_id, work_oa_id) ∈ ledger.removed_edges` → skip. After iterating real authorships, iterate `ledger.added_edges` and feed them to the same writer. |
| `a2_init_atts::add_author_atts` | When two authors are aliased, merge their text attributes: pick keep's name and ORCID (the ORCID of the owner who submitted the merge), union wiki slugs (prefer keep's if both set), sum raw_cites / raw_works before the downcasting write. |
| `a2_init_atts::add_work_atts` | When two works are aliased, pick the keep's DOI, name, year; the drop's data is discarded (it's the duplicate). |
| end of `derive_links5` (or a new `a3_finalize`) | Call `UserLedger::write_manifest`. |

Bootstrap-safety review: all these changes use types already existing in
`gen/a1_entity_mapping.rs` by the time they run, so no metaprogramming loop
violation. Adding `UserLedger::load` before `filter.rs` is safe because the
ledger file is external data, not dmove-generated.

### 6.4 Export step

```
pyscripts/export_user_ledger.py

- Connects to data/rankless.sqlite.
- SELECT * FROM ledger_events WHERE revoked_at IS NULL
    AND moderation IN ('auto_ok', 'accepted')
- For each event, resolve payload references that are already resolvable from
  the previous run's outputs (optional; the pipeline re-resolves anyway).
- Collapse counter-events: if a 'revoke' event targets an event_id that is in
  the applied set, emit a synthetic "undo" instruction; if it targets a still-
  pending event, DON'T include either in active.jsonl.
- Write $OA_ROOT/user_ledger/active.jsonl (one event per line).
- Write $OA_ROOT/user_ledger/snapshot_manifest.json with the frozen set of
  event_ids and a generated run_id (ISO timestamp).
```

Hooked into `Makefile` as a dependency of `filter`:

```
filter: export-ledger clean-filters clean-keys clean-cache
    cargo run --release -p rankless-rs -- filter $(OA_ROOT)

export-ledger:
    uv run -m pyscripts.export_user_ledger $(OA_ROOT)
```

---

## 7. API surface

### 7.1 Consolidation of existing endpoints

| Existing endpoint | Replaced by |
|-------------------|-------------|
| `POST /api/papers/disown` | `POST /api/ledger` with `{kind:"disown_paper", payload:{wid}}` |
| `DELETE /api/papers/disown` | `DELETE /api/ledger/:event_id` (pending) OR `POST /api/ledger` with `{kind:"revoke", payload:{target_event_id}}` (applied) |
| `POST /api/papers/claim` | `POST /api/ledger` with `{kind:"claim_paper", …}` |
| `DELETE /api/papers/claim` | as above |
| `POST /api/papers/merge` | `POST /api/ledger` with `{kind:"merge_papers", …}` |
| `DELETE /api/papers/merge` | as above |
| `POST /api/authors/merge-request` | `POST /api/ledger` with `{kind:"merge_authors", …, moderation:"pending_review"}` |

Single handler `src/routes/api/ledger/+server.ts`:

```ts
POST   { kind, payload }                    -> creates event, returns event_id
GET    ?orcid=…                             -> lists events for the caller
DELETE /api/ledger/:event_id                -> soft-delete (only if still pending)
PATCH  /api/ledger/:event_id { payload }    -> edit pending event (dedup-aware)
```

For edits to *applied* events, the client issues a `POST` with
`{kind: "revoke", payload: {target_event_id}}` and (optionally) a follow-up
`POST` with a replacement event (e.g. re-merge into a different target).
The UI hides this behind a "change this" button.

### 7.2 New lookup endpoint

`GET /api/ledger-status` → passes through the server's loaded
`applied_manifest.json` (with `run_id` + `applied_event_ids` + `skipped`).
Used by `+page.server.ts` to partition the user's events.

---

## 8. Frontend

### 8.1 Components

- Extract `src/lib/components/AuthorLedgerPanel.svelte`. Replaces
  `AuthorOwnerTools.svelte` and absorbs the disown/merge UI from
  `AllWorks.svelte` (the paper-row actions still live there, but they POST
  to the unified endpoint; the confirmation/undo bar moves into the panel).
- New subcomponents: `LedgerEventRow.svelte` (renders one event by kind),
  `LedgerStatusBadge.svelte` (`Applied` / `Pending` / `Queued for review` /
  `Skipped` chip with tooltip).

### 8.2 Page layout on `author-papers/[...]/+page.svelte`

```
[Name header — impact summary]

[Immediate Impact DAG]

[AllWorks list] (unchanged visually; per-row actions still dispatch events)

┌── Your Profile Changes ─────────────────────────────────┐
│                                                          │
│  Applied (N)              ← collapsible, default open   │
│    • Disowned "Foo et al. 2019"    [change] [undo]      │
│    • Merged "Bar 2018" into "Bar 2018 preprint"  [undo] │
│                                                          │
│  Pending — next data refresh (M)   ← collapsible        │
│    • Claim DOI 10.1234/x …               [edit] [×]     │
│    • Revoke: un-disown "Foo et al. 2019" [×]            │
│                                                          │
│  [+ Disown a paper] [+ Claim by DOI]                     │
│  [+ Merge two of my papers] [+ Merge another profile]    │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### 8.3 Editability semantics

- **Pending events**: `PATCH` or `DELETE` against their `event_id`. Instant.
- **Applied events**: `[undo]` creates a counter (`revoke`) event — becomes
  Pending. `[change]` creates a counter event *and* opens the create-form
  pre-filled with the old payload — user can submit a modified version.
- Visual cue for applied-but-countered: strikethrough in Applied list +
  a matching entry in Pending. User sees the causal pair.

### 8.4 Data wiring

`+page.server.ts` load additions:

```ts
const [events, manifest] = await Promise.all([
  LedgerDb.getEventsForOrcid(locals.user.orcid),
  fetchLedgerStatus()      // calls /api/ledger-status, cached briefly
]);
const appliedSet = new Set(manifest.applied_event_ids);
const applied = events.filter(e => appliedSet.has(e.event_id) && e.kind !== 'revoke');
const pending = events.filter(e => !appliedSet.has(e.event_id) && !e.revoked_at);
return { …, applied, pending, runId: manifest.run_id };
```

The existing `disownedWids` / `mergedPairs` / `claimedDois` props continue to
be derived from *active, non-revoked* events, so `AllWorks.svelte` keeps
working unchanged. For pending undo-of-applied-disown events, we exclude
the original disown from the derived `disownedWids` set (otherwise the paper
keeps hiding) — see §9 point 5 for the reconciliation logic.

---

## 9. Invariants and edge cases (checklist)

1. **Idempotent POSTs**: the unique index on `(orcid, kind, subject_hash)`
   makes duplicate events a no-op.
2. **Revoke of revoke**: undoing a counter-event is just deleting the
   pending counter — never creates a second counter.
3. **Alias cycles**: if an event says "merge A into B" and another says
   "merge B into A," collapse to a single edge, pick by lower `event_id`.
4. **Chained merges**: A→B, B→C. `UserLedger::resolve` computes transitive
   closure before exposing `author_aliases`; the map is path-compressed.
5. **UI reconciliation of counter-events**: `disownedWids` is derived as
   `appliedDisowns ∖ { wid : ∃ pending revoke targeting the disown event }`
   ∪ `pendingDisowns`. Keep this logic in one utility, not inline in
   components.
6. **Pending event referencing an as-yet-unknown author**: author-merge by
   semantic-id resolves at export time against the currently-loaded server
   snapshot; if the other profile doesn't exist yet, export records
   `skipped` with reason and keeps the event for future runs.
7. **Owner pinning cascade**: if an owner pins themselves and then disowns
   all works, the author entity still exists but has zero works → must not
   break `hit_papers` or any `per-author` iteration that assumes ≥1 work.
   Audit all loops over `Authors` for empty-work handling.
8. **Revoked events and the `WHERE revoked_at IS NULL` partial index**: the
   partial unique index allows re-submitting a previously-revoked event —
   intended behaviour (user changed their mind).
9. **Moderation pipeline**: events with `moderation = 'pending_review'`
   are not in `active.jsonl`. An admin UI (Phase 2) flips them to `accepted`,
   which *then* lets the next export include them.

---

## 10. Security / abuse mitigations

- API creation of any event requires `locals.user.orcid`. The *subject* of
  an event is always the authenticated ORCID — users cannot edit another
  owner's profile.
- Rate-limit `POST /api/ledger` (e.g. 30 events/hour/ORCID) in the SvelteKit
  handler. Trivial bounds check in-memory; the ledger table growth is bounded.
- Log every event creation with source IP at the web layer (outside this
  plan, but note in `hooks.server.ts`).
- The pipeline honours no network input — snapshot file is the only channel.

---

## 11. Observability

- `UserLedger` writes `applied_manifest.json` including `skipped` reasons.
- On `/ledger-status` the server exposes the same. Surfaced as a chip on
  "skipped" events in the UI with tooltip (`orcid_not_in_dataset`,
  `doi_not_found`, `wid_not_found`, `alias_cycle_collapsed`, etc.).
- Add to the `status_dump.sh` script: include
  `$OA_ROOT/user_ledger/applied_manifest.json` in the dump.

---

## 12. Implementation plan — ordered tasks

Each phase is self-contained and should leave the tree green. Phases 1–3 can
ship incrementally (existing UI keeps working via the view layer). Phase 4
is the pipeline integration; Phase 5 is UI polish.

### Phase 1 — Ledger store
1. Add `LedgerDb` to `src/lib/server/db.ts` (alongside `PaperDb`) with
   `createEvent`, `revokePending`, `editPending`, `getEventsForOrcid`,
   `getSubjectHash` helpers. Create `ledger_events` table in the same
   `getDb()` init block.
2. Write `pyscripts/migrate_ledger.py` that, given an existing
   `rankless.sqlite`, bulk-inserts rows from the four legacy tables into
   `ledger_events` (preserving `created_at`), then drops the legacy tables.
   Idempotent (skips if `ledger_events` already populated).
3. Tests: unit test the subject-hash dedup and revoke semantics.
4. Update `docs/details/tree-description.md` §"Server Utilities" to reference
   `LedgerDb`.

### Phase 2 — API consolidation
1. Create `src/routes/api/ledger/+server.ts` (`POST`, `GET`, `DELETE`,
   `PATCH`). Back `POST` with `LedgerDb.createEvent`; validate
   `locals.user.orcid` matches the subject.
2. Rewrite each of `api/papers/disown`, `api/papers/claim`,
   `api/papers/merge`, `api/authors/merge-request` to proxy through
   `LedgerDb`. Keep the old URLs for backward compat in this phase so the
   existing UI keeps functioning; they become thin wrappers.
3. `+page.server.ts` load: derive `disownedWids` / `mergedPairs` /
   `claimedDois` / `authorMergeRequests` from `LedgerDb.getEventsForOrcid`
   instead of the legacy `PaperDb.*` calls. (Legacy tables are empty after
   Phase 1 migration.)
4. Remove `src/lib/server/db.ts` `PaperDb` exports once call sites are gone.

### Phase 3 — Export + manifest (no pipeline changes yet)
1. Add `pyscripts/export_user_ledger.py` producing `active.jsonl` and
   `snapshot_manifest.json` under `$OA_ROOT/user_ledger/`.
2. `Makefile`: `export-ledger` target; make `filter` depend on it.
3. Server: add `/api/ledger-status` that reads
   `$OA_ROOT/user_ledger/applied_manifest.json` (if absent, returns
   `{run_id: null, applied_event_ids: []}` — equivalent to "no pipeline has
   ever consumed any events yet").
4. This phase adds the plumbing but no pipeline effect. It's safe to
   deploy: the manifest is empty, every event shows `Pending`.

### Phase 4 — Pipeline integration
1. Create `rankless_rs/src/common/user_ledger.rs`. Implement `load`,
   `resolve` (two streaming passes over `authors/main` and `works/main`),
   transitive closure for aliases, `owner_pins` population.
2. `filter.rs`: load `UserLedger` early; adjust `count_passes` to group by
   alias root; add `owner_pins` override. Modify edge iteration to apply
   `removed_edges` / `added_edges`.
3. `a1_entity_mapping::main`: wire alias map into the `Authors` and `Works`
   builders so drop-side OA ids never get their own dm_id. Emit
   `discarded_authors` correctly for aliased drops.
4. `a2_init_atts::add_ship_relations::proc_next`: filter `removed_edges`;
   after CSV iteration, iterate `added_edges` and feed the writer.
5. `a2_init_atts::add_author_atts` and `add_work_atts`: merge attribute
   fields per alias group (names, orcids, wikislugs, years, dois, biblios).
6. Emit `applied_manifest.json` at the end of the last step (or via a tiny
   `a_finalize` stage).
7. Tests: extend `rankless_rs` tests with a small fixture dataset that
   includes a handful of ledger events; assert dm_id collapse, authorship
   delta, citation sums, filter survival.

### Phase 5 — Frontend ledger panel
1. Extract `AuthorLedgerPanel.svelte`, `LedgerEventRow.svelte`,
   `LedgerStatusBadge.svelte`.
2. Wire `+page.server.ts` load to fetch applied manifest + events, split,
   and pass to the page.
3. Refactor `AllWorks.svelte` confirm/undo bars — forward events to the
   panel via a shared store (avoid prop drilling per CLAUDE.md).
4. Implement counter-event (`revoke`) UX for the Applied section; default
   banner text: "Queued — will apply at next data refresh (run_id X)."
5. Remove `AuthorOwnerTools.svelte` (content absorbed).
6. Update `docs/details/tree-description.md` with the new components.

### Phase 6 — Cleanup & docs
1. Delete the legacy `api/papers/{disown,claim,merge}` and
   `api/authors/merge-request` wrappers.
2. Delete legacy SQLite tables (migration script from Phase 1 already did
   this on staging; add a one-shot migration for prod).
3. Update `docs/overview.md` architecture diagram to include the ledger
   flow.
4. Delete `AuthorMergeRequest` type from `lib/tree-types.ts` if no longer
   referenced.

---

## 13. Validation plan

- Unit tests: `pyscripts/tests/test_export_user_ledger.py` covers collapse
  of counter-events, alias transitive closure, orphan handling.
- Integration test: `rankless_rs` fixture dataset (`local-moks/`) with
  `user_ledger/active.jsonl` applied; assert expected dm_ids, work counts,
  citation sums, authorship sets.
- End-to-end test in `tests/` (Playwright): ORCID dev-login → POST ledger
  events → refresh page → see Pending entries; simulate a pipeline run by
  writing a fake `applied_manifest.json` → reload page → see Applied entries
  + absent Pending entries.
- Branch-comparison (`pyscripts/branch_comparison.py`): run the current
  implementation vs the ledger implementation on a dataset with no events,
  expect structural equality. With events, expect deterministic divergence
  only at the affected entities.

---

## 14. Deferred follow-ups (not in this plan)

- `add_paper_request` full implementation: needs a synthetic-CSV injection
  step (prepend to `works/main` with a generated OA id in a reserved range),
  DOI resolution fallback, and moderation UI.
- Admin dashboard for `pending_review` events.
- E-mail notifications on Applied transitions.
- Cross-owner conflict resolution UI.
- Per-event "diff preview" (what will change in the author's numbers when
  this event lands) — requires a lightweight dry-run in the server.
