# Author Profile Modification Ledger

> Persistent, user-authored modifications to author profiles (ORCID-authenticated)
> that flow into the pipeline at the earliest possible stage and cascade through
> every downstream artefact. This document is the architecture reference and
> work breakdown; agents/humans executing it should follow the phases in order
> and delete completed sections as they land (per the repo planning convention).

---

## 1. Problem statement

A logged-in ORCID owner on `/authors/<semantic-id>/` can today:

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

1. Survives pipeline re-runs (the data product is re-built from CSVs on demand).
2. Is **applied as early as possible** inside the pipeline so every downstream
   artefact reflects the edit (not just the author's own paper list).
3. Distinguishes, per user, between **already-applied** events (consumed by the
   last pipeline run) and **pending** events (queued for the next run).
4. Allows both sets to be edited; edits to applied events produce new
   counter-events (the log is immutable).
5. Is extensible: the same mechanism must accept **future user actions**
   (add-a-paper-that-isn't-in-OpenAlex, self-removal, affiliation correction, …).
6. **Survives ID churn.** Any link in the
   `dm_id ↔ openalex_id ↔ orcid/doi ↔ semantic_id` chain can break between
   runs. The ledger must remain resolvable and auditable regardless.

---

## 2. Locked decisions

These are settled and drive the rest of the document. No agent should
revisit them without user sign-off.

- **Moderation is not uniform.** Default `moderation` per kind:
  - `disown_paper` → `auto_ok`
  - `merge_papers` → `auto_ok`
  - `merge_authors` → `pending_review` (requires human accept)
  - `claim_paper` → `pending_review` (requires human accept; claims are the
    highest-risk action — treat as untrusted until reviewed)
  - `add_paper_request` → `pending_review` (deferred; schema reserved only)
- **Owner pinning is a separate filter concept**, not a side-effect of
  having submitted events. Any ORCID that has ever authenticated *and*
  either owns ≥1 work or has submitted a ledger event is pinned into the
  keep-filter so they can always log in to manage their profile. See §7.
- **Applied events are immutable.** UI "edit" of an applied event creates a
  new pending `revoke` counter-event (plus an optional replacement event).
  The log grows monotonically; the `applied_manifest.json` of each run is a
  permanent record.
- **Single `ledger_events` table** — the four legacy per-action tables are
  migrated and deleted (phase 1).
- **Ledger payloads store stable IDs** (OpenAlex OA id primarily, with DOI
  and ORCID as fallbacks and a display-time snapshot). They never store
  `dm_id` or `semantic_id` because both are per-run artefacts. Resolution
  happens at event-creation time and again at each pipeline run; see §6.

---

## 3. Resolved policy decisions (locked 2026-04-27)

1. **Claim validation.** API rejects claims whose DOI is (a) malformed
   or (c) already bound to a different ORCID in the current data; accepts
   (b) unresolvable-against-current-data as pending (next OpenAlex
   snapshot may include it).
2. **Author-merge direction.** Submitter is always the keep side. Moderator
   can only accept/reject — never swap. A swap requires a new event by the
   other party authenticating with their own ORCID.
3. **Rate limits.** 60 events/ORCID/day overall; 10/day for `claim_paper`
   and `merge_authors`.
4. **Counter-event moderation.** `revoke` of any applied event always
   inherits `auto_ok` (risk was cleared at the original apply).
5. **Pipeline-run concurrency.** No write lock during pipeline runs.
   Snapshot is taken at pipeline start; later writes are pending after
   the run.

## Notes on staged delivery

- Phases 1–5 ship without a moderator UI. `pending_review` events
  accumulate during this window with no surfaced action — accepted as a
  known limitation; resolved when Phase 6 lands the `/moderate` queue.
- The legacy display-layer compat shim (`getLegacyOwnerData`) has been
  removed. Owner data fields (`disownedWids`, etc.) return empty until
  the Phase 5 ledger panel UI replaces them.

---

## Status (2026-04-28)

Phases 1–3 are committed. Phase 4 implementation is complete; the
integration test (§15) is the remaining gate before commit.

---

## 4. Scope

### 4.1 In scope (this plan)
- Unified append-only `ledger_events` table (SQLite, same DB as today).
- Multi-ID payload schema with stable-ID resolution (§6).
- Snapshot export: SQLite → `$OA_ROOT/user_ledger/active.jsonl` before `filter`.
- Pipeline ingest module consumed by `filter.rs`, `a1_entity_mapping`, `a2_init_atts`.
- Post-run `applied_manifest.json` written alongside pipeline output.
- Server reads the manifest and exposes applied/pending/skipped status.
- Frontend: two panels on the author page (Applied / Pending), plus
  consolidation of today's scattered `AuthorOwnerTools` / `AllWorks`
  actions into a single ledger UI.
- Moderator workflow + queue page (streamlined review).
- Owner-pinning as a distinct filter stage.

### 4.2 Out of scope (Phase 2+)
- Full `add_paper_request` implementation (schema allocation only — no
  CSV-injection pipeline).
- `claim_paper` pipeline effect (stays `pending_review` with no default
  applier; needs dedicated follow-up on authorship synthesis — see §6.8).
- E-mail / notification to the user when a queued event lands.
- Cross-owner conflict resolution UI.

---

## 5. Architecture overview

```
┌───────────────────────────────────────────────────────────────────────┐
│ Browser (AuthorLedgerPanel.svelte, ModeratorQueue.svelte)             │
│   └─ POST/GET/DELETE/PATCH /api/ledger/* ──────────────┐              │
└────────────────────────────────────────────────────────┼──────────────┘
                                                         ▼
┌───────────────────────────────────────────────────────────────────────┐
│ SvelteKit server                                                      │
│   LedgerDb                (append-only ops on ledger_events)          │
│   id_resolver             (dm_id / semantic_id → stable OA id)        │
│   +page.server.ts         (joins applied_manifest.json)               │
└───────────────────────────────────────────────────────────────────────┘
                                         ▼  (shared SQLite file)
┌───────────────────────────────────────────────────────────────────────┐
│ data/rankless.sqlite                                                  │
│   ledger_events           (append-only, soft-revoke of pending only)  │
│   ledger_runs             (manifest history per pipeline run)         │
│   owner_pins              (pinned ORCIDs)                             │
└───────────────────────────────────────────────────────────────────────┘
                                         ▲
                                         │  pre-run export
                                         │
┌───────────────────────────────────────────────────────────────────────┐
│ pyscripts/export_user_ledger.py                                       │
│   reads ledger_events (revoked_at IS NULL AND moderation IN OK_SET)   │
│   writes $OA_ROOT/user_ledger/{                                       │
│     active.jsonl              (normalised events)                     │
│     owner_pins.txt            (ORCIDs to pin through filter)          │
│     snapshot_manifest.json    (run_id, event_ids included)            │
│   }                                                                   │
└───────────────────────────────────────────────────────────────────────┘
                                         ▼
┌───────────────────────────────────────────────────────────────────────┐
│ rankless_rs pipeline                                                  │
│   common/user_ledger.rs  (load + resolve stable ids → BigId → dm_id)  │
│   filter.rs              — consult alias map, pin owners              │
│   a1_entity_mapping      — alias author + work BigIds before dm_id    │
│   a2_init_atts           — drop/inject authorships, merge attrs       │
│                                                                       │
│ at end of run: writes $OA_ROOT/user_ledger/applied_manifest.json      │
│   { run_id, applied_event_ids, skipped: [{event_id, reason, …}] }     │
└───────────────────────────────────────────────────────────────────────┘
                                         ▼
┌───────────────────────────────────────────────────────────────────────┐
│ rankless_server (on startup)                                          │
│   reads applied_manifest.json → exposes /api/ledger-status            │
│   also: /api/resolve-entity for the UI (stable-id lookups)            │
└───────────────────────────────────────────────────────────────────────┘
```

### 5.1 State transitions per ledger event

```
                 ┌──────────┐  export snapshot   ┌──────────┐
  POST /api/…    │ pending  │ ─────────────────▶ │ in-run   │
  ────────────▶  │          │ ◀─── revoke ────── │ (frozen) │
                 └──────────┘                    └──────────┘
                       │                              │
                       │  DELETE (soft)               │ pipeline commit
                       ▼                              ▼
                 ┌──────────┐                    ┌──────────┐
                 │ revoked  │                    │ applied  │
                 │          │                    │          │
                 └──────────┘                    └────┬─────┘
                                                      │
                                                      │ user clicks
                                                      │ "undo"/"change"
                                                      ▼
                                           ┌────────────────────┐
                                           │ counter-event      │
                                           │ (new pending row,  │
                                           │  kind = 'revoke',  │
                                           │  points at target) │
                                           └────────────────────┘
```

- `pending` → user created an event; not yet in any run's snapshot.
- `in-run` → snapshot taken; pipeline executing. Soft deletes blocked.
- `applied` → pipeline consumed it; manifest lists its event_id. Immutable.
- `revoked` → user cancelled while still pending (before snapshot). Soft delete.
- `counter_pending` → an applied event was "undone" in the UI; a new
  `revoke` event refers to it by `event_id`. Next pipeline run un-does.

### 5.2 Moderation pipeline

Every event has a `moderation` column. Only events with
`moderation IN ('auto_ok', 'accepted')` and `revoked_at IS NULL` are
exported to `active.jsonl`.

| Event kind | Default `moderation` | Moderator action required? |
|------------|----------------------|----------------------------|
| disown_paper | auto_ok | No |
| merge_papers | auto_ok | No |
| revoke (counter) | auto_ok (inherit) | No |
| merge_authors | pending_review | Yes — accept/reject |
| claim_paper | pending_review | Yes — accept/reject |
| add_paper_request | pending_review | Yes (deferred) |

Moderators are identified by a flag on the user session (implementation
detail: add `MODERATOR_ORCIDS` env var, expand later). A moderator's
action is itself a ledger event of kind `moderation_decision` with
`payload: {target_event_id, decision, reason}`, so decisions are audited
through the same log. This second-order event does not need a pipeline
effect; it only mutates the `moderation` column of its target (via a
single UPDATE — the only permitted mutation in the table).

---

## 6. ID stability and resolution

This is the most fragile part of the system. The identifier chain is:

```
┌─────────┐   generated per-run    ┌──────────────┐
│ dm_id   │ ◀──────────────────── │ semantic_id  │  (unstable per run)
└─────────┘                        └──────────────┘
     ▲                                    ▲
     │  per-run                           │  per-run
     │  (a1_entity_mapping)               │
     │                                    │
┌────┴─────────────────────────────────────┴───┐
│        OpenAlex id (BigId, 64-bit)            │  ← authoritative upstream
└───────────────────────────────────────────────┘
     ▲                ▲
     │                │
     │                │
┌────┴────┐      ┌────┴────┐
│  ORCID  │      │   DOI   │   ← external world, stable but
└─────────┘      └─────────┘     imperfect (preprint vs published,
                                 redirects, sometimes missing)
```

Any arrow can break between runs. A disown event persisted against a
`dm_id` or `semantic_id` is toxic — the same physical work probably has a
different dm_id next run due to different sort order, filter thresholds,
or simply a later CSV snapshot.

### 6.1 Stored identifiers per event subject

Every event payload stores a **subject** block with as many identifier
layers as possible, captured at event-creation time:

```jsonc
// A "work subject" (appears in disown_paper, merge_papers, claim_paper)
{
  "oa_id": 123456789,               // OpenAlex numeric id, primary
  "doi": "10.1234/foo.bar",         // optional; canonicalized lower-case
  "dm_id_at_creation": 4711,        // for audit only; never used for resolve
  "semantic_id_at_creation": "...", // for audit only
  "run_id_at_creation": "...",      // which pipeline run the above were from
  "display_snapshot": {              // for orphan UI rendering
    "title": "Foo et al. 2019",
    "year": 2019,
    "first_author_name": "..."
  }
}

// An "author subject" (appears in merge_authors and owner-side fields)
{
  "oa_id": 501234567,
  "orcid": "0000-0001-2345-6789",
  "dm_id_at_creation": 1234,
  "semantic_id_at_creation": "jane-doe-7",
  "run_id_at_creation": "...",
  "display_snapshot": {
    "display_name": "Jane Doe",
    "institutions_at_creation": ["inst-oa-id-1", "inst-oa-id-2"]
  }
}
```

`oa_id` is the **primary** identifier. `doi`/`orcid` are secondary fallbacks.
`dm_id_at_creation` and `semantic_id_at_creation` are stored purely as
provenance (so we can display "Last known as Jane Doe (jane-doe-7) in run X")
— never used during resolution.

### 6.2 Resolution algorithm (pipeline side)

Implemented in `rankless_rs/src/common/user_ledger.rs::UserLedger::resolve`.
Runs once per pipeline after the CSVs are available, before `filter.rs`:

```
for each event in active.jsonl:
    for each subject in event:
        oa_id_final = None
        # 1. Try primary oa_id against current ID mapping
        if subject.oa_id in current_oa_ids:
            oa_id_final = subject.oa_id
        # 2. Try OpenAlex merged_ids redirect
        elif subject.oa_id in merged_ids_redirect:
            oa_id_final = merged_ids_redirect[subject.oa_id]
        # 3. For works: fall back to DOI lookup (doi_to_oa)
        elif kind == work and subject.doi:
            oa_id_final = doi_to_oa.get(canonicalize(subject.doi))
        # 4. For authors: fall back to ORCID lookup (orcid_to_oa)
        elif kind == author and subject.orcid:
            oa_id_final = orcid_to_oa.get(subject.orcid)

        if oa_id_final is None:
            skipped.push((event_id, ResolveFail{subject_idx, reasons}))
            break  # whole event skipped if any subject unresolvable

# Events that successfully resolved all subjects are added to:
#   author_aliases, work_aliases, removed_edges, added_edges, owner_pins
# Events that fail resolution are recorded in skipped[] with a reason
# and are RE-TRIED on the next run — they are NOT revoked. If the
# data finally contains the subject, the event resolves and applies.
```

Supporting lookups constructed at pipeline start:

- `current_oa_ids` — built from the freshly-parsed `authors/main` and
  `works/main` CSVs before `a1`.
- `merged_ids_redirect` — consumed from the OpenAlex `merged_ids` files
  (the snapshot publishes these; see §6.5).
- `doi_to_oa` — single streaming pass over `works/main` CSV.
- `orcid_to_oa` — single streaming pass over `authors/main` CSV.

### 6.3 Resolution at event-creation time (Node side)

When a user POSTs an event, the SvelteKit handler must populate every
identifier layer it can from the currently-served data. This prevents
zombie events — an event created against a stale UI state with no
fallbacks.

New server helper `src/lib/server/id_resolver.ts`:

```ts
// Resolves the UI's view of an entity to the stable-id block stored in the
// payload. Throws 422 if the minimum (oa_id OR a usable fallback) can't
// be obtained — the client must refresh and retry.
async function resolveWorkSubject(input: {
  wid?: number; doi?: string; semantic_id?: string;
}): Promise<WorkSubject>;

async function resolveAuthorSubject(input: {
  semantic_id?: string; orcid?: string; dm_id?: number;
}): Promise<AuthorSubject>;
```

Implementations hit small new Rust endpoints:

- `GET /v1/resolve/work?wid=…` → `{ oa_id, doi, semantic_id, display }`
- `GET /v1/resolve/work?doi=…` → same
- `GET /v1/resolve/author?semantic_id=…` → `{ oa_id, orcid, display }`
- `GET /v1/resolve/author?orcid=…` → same

The server already has all the needed structures loaded (orcids, dois,
semantic_ids, name cache). These endpoints add only trivial code.

### 6.4 Paper type extension

`src/lib/tree-types.ts::Paper` gets a new optional field:

```ts
export type Paper = {
  wid: number;          // dm_id, per-run; used by /works/* endpoints
  oaId: number;         // OpenAlex BigId, stable; used in ledger payloads
  // …
};
```

Also `SearchResult` gains `oaId?: number`. The server populates these in
the existing response shaping in `rankless_server`. **This is a
cross-cutting change** (all paper list responses need it) but it's a
one-line addition per shaping site.

### 6.5 OpenAlex `merged_ids` ingestion

OpenAlex publishes monthly `merged_ids/` tables mapping deprecated IDs to
their canonical counterparts. Today the pipeline ignores them.

Add a one-shot load at the top of the pipeline:

- `rankless_rs/src/common/merged_ids.rs`: `load_merged_ids(root: &Path) -> HashMap<BigId, BigId>`
- Called from `UserLedger::resolve` (used in step 2 of the algorithm above).
- Also useful beyond the ledger: the `oa-id/[oaId]/+server.ts` redirect
  route can consult it for stale OA ids that show up in external links.
  (Out of scope here — mention only.)

### 6.6 Orphan state machine

An event whose subjects can't be resolved in the current run is **orphan
for that run**. Orphans are not revoked — they sit patiently and retry
next run.

UI treatment: in the Pending section we render orphans with a distinct
chip (`Could not resolve in last run`) and a tooltip listing the reason
codes returned in `skipped[]`. The user can `[×]` them (soft delete) or
`[edit]` them to supply better identifiers (e.g. correct the DOI).

Reason codes emitted to `applied_manifest.json`:

- `oa_id_not_in_dataset` — primary id no longer present, no fallback hit.
- `doi_not_found` — DOI fallback didn't match.
- `orcid_not_in_dataset` — owner's ORCID has no author entity (filter drop).
- `alias_cycle_collapsed` — event was part of a cycle and was deduplicated.
- `authority_violation` — submitter ORCID isn't on either side of the subject.
- `superseded_by_event` — a later event by the same owner made this moot.

### 6.7 Display-side resolution (server → UI)

The author page load (`+page.server.ts`) shows the user their events.
For each event we need human-readable text for each subject. Resolution
order for display:

1. Look up the subject's `oa_id` via the current server data → if found,
   use the live display text (fresh, shows current title / current author
   name).
2. Else, fall back to `display_snapshot` in the payload. Render with a
   "as of run X" tooltip.
3. Else, show `oa_id`/`orcid`/`doi` verbatim with a generic "No longer in
   data" hint.

This logic lives in `src/lib/utils/ledger-display.ts`. Pure function,
unit-testable against a synthetic `paperMap`.

### 6.8 Claim injection — deferred but schema-ready

`claim_paper` is marked `pending_review`. Moderator accept flips it to
`accepted`. The pipeline *could* then synthesise an authorship row
(`added_edges`), but that requires deciding:

- Which `Authorships` row id to assign (these aren't user-visible, so
  likely just append to the authorship entity with the owner's dm_id and
  the work's dm_id).
- Whether to also update `inst` relations (claim without institution
  information).

Phase-1 pipeline **skips** claim events entirely with reason
`claim_pipeline_not_implemented`. Phase-2 work resolves this. Until then,
accepted claims are display-only (the author's profile shows them as
"claimed (display only)" in the Pending list; the manifest records them
as skipped).

### 6.9 Integrity invariants (tested)

- Round-trip: take a ledger event, resolve it, write it, re-read it —
  subject IDs match.
- Stale dm_id safety: a disown event with `dm_id_at_creation = 4711`
  is resolved solely via `oa_id`; changing the pipeline's dm_id
  assignment does not change resolution.
- Merged-id redirect: an event whose primary `oa_id` has been deprecated
  resolves to the redirect target; this is logged as
  `{event_id, redirected: {from, to}}` in `applied_manifest.json`.
- Alias transitivity: A→B, B→C, D→B collapses to a single root C with
  path-compression. Stored in `author_aliases` / `work_aliases` as a flat
  `drop → root` map (no chains).

---

## 7. Data model

### 7.1 `ledger_events`

```sql
CREATE TABLE ledger_events (
  event_id       INTEGER PRIMARY KEY AUTOINCREMENT,
  orcid          TEXT NOT NULL,           -- submitter
  kind           TEXT NOT NULL,           -- see §5.2 and §6.1
  payload        TEXT NOT NULL,           -- JSON, one subject block per subject
  subject_hash   TEXT NOT NULL,           -- sha1 of sorted stable ids; for dedup
  created_at     TEXT NOT NULL DEFAULT (datetime('now')),
  revoked_at     TEXT,                    -- soft-delete; only for still-pending
  moderation     TEXT NOT NULL
                 DEFAULT 'auto_ok',       -- 'auto_ok'|'pending_review'|'accepted'|'rejected'
  moderated_by   TEXT,                    -- ORCID of moderator, if any
  moderated_at   TEXT
);

CREATE INDEX idx_le_orcid ON ledger_events(orcid);
CREATE INDEX idx_le_kind ON ledger_events(kind);
CREATE INDEX idx_le_moderation ON ledger_events(moderation);
CREATE UNIQUE INDEX idx_le_dedup
  ON ledger_events(orcid, kind, subject_hash)
  WHERE revoked_at IS NULL;
```

### 7.2 `ledger_runs`

```sql
CREATE TABLE ledger_runs (
  run_id         TEXT PRIMARY KEY,        -- ISO timestamp, generated at export
  snapshot_at    TEXT NOT NULL,           -- when active.jsonl was frozen
  manifest_at    TEXT,                    -- when applied_manifest.json landed
  manifest_json  TEXT                     -- full manifest, for audit / rollback
);
```

Server polls `$OA_ROOT/user_ledger/applied_manifest.json` on startup and,
if it's newer than the newest `ledger_runs.run_id`, inserts a row. This
gives us a permanent audit trail of which runs consumed which events
without needing to re-parse manifest files.

### 7.3 `owner_pins`

```sql
CREATE TABLE owner_pins (
  orcid          TEXT PRIMARY KEY,
  first_seen_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
```

Populated on each successful ORCID login. Login is a prerequisite for any event submission, so pinning on login is sufficient.
Exported to `$OA_ROOT/user_ledger/owner_pins.txt` (one ORCID per line,
plain text) consumed by `filter.rs`. This is **independent** of the
event ledger — a user who logs in never loses the ability to see their
profile even if they've never submitted a ledger event.

### 7.4 Payload shapes

All payloads carry stable-ID subject blocks (§6.1).

```jsonc
// disown_paper
{ "work": WorkSubject }

// claim_paper
{ "work": WorkSubject }                  // oa_id optional here — DOI primary

// merge_papers
{ "keep": WorkSubject, "drop": WorkSubject }

// merge_authors (submitter is always the keep side)
{ "keep": AuthorSubject, "drop": AuthorSubject, "note": "..." }

// revoke (counter-event)
{ "target_event_id": 12345, "reason": "..." }

// moderation_decision (moderator-only)
{ "target_event_id": 12345, "decision": "accepted"|"rejected", "reason": "..." }

// add_paper_request (deferred)
{ "work_claim": { doi, title, year, venue, authors: [AuthorSubject|string] } }
```

`subject_hash` is computed from **canonicalised stable ids only** — order-
independent within a kind (for `merge_papers`, the pair is sorted
numerically; for `merge_authors`, ORCIDs are sorted lexically if both
present, otherwise OA ids). This makes dedup robust to the UI picking
either paper as "keep."

### 7.5 Applied manifest

`$OA_ROOT/user_ledger/applied_manifest.json`:

```jsonc
{
  "run_id": "2026-04-22T10:00:00Z",
  "snapshot_at": "2026-04-22T09:58:12Z",
  "applied_event_ids": [42, 43, 47, 50, 51],
  "redirected": [
    { "event_id": 47, "subject": "keep",
      "from": 123456789, "to": 987654321 }
  ],
  "skipped": [
    { "event_id": 48, "reason": "orcid_not_in_dataset" },
    { "event_id": 49, "reason": "doi_not_found" },
    { "event_id": 52, "reason": "claim_pipeline_not_implemented" }
  ]
}
```

---

## 8. Pipeline integration (architecture reference)

The implementation lives in `rankless_rs/src/user_ledger.rs` and
`rankless_rs/src/merged_ids.rs`. Touchpoints: `filter.rs` (alias-aware
PersonAuthorship counting + owner-pin author filter),
`a1_entity_mapping.rs` (skip drop-side oa_ids; write `a1_manifest.json`),
`a2_init_atts.rs` (augment `LoadedIdMap` with drop→keep dm aliases;
filter `removed_edges` in `ShipRelWriter::proc_next`; merge attributes
into the keep side; write `applied_manifest.json`).

Export pipeline: `pyscripts/export_user_ledger.py` is hooked from
`Makefile` so `filter` depends on `export_user_ledger`.

Revoke semantics: the export step inlines the target event into a
`revoke` event as `target_inlined`. Rust reverses the inlined target
without reading SQLite.

Open items from this section are tracked in **Status (2026-04-28)**
above.

---

## 9. API surface — remaining

Ledger CRUD, status, and resolve endpoints are committed. Phase 6 adds:

```ts
GET  /api/moderation/queue                 // pending_review events; mod-only
POST /api/moderation/:event_id/decide      // accept/reject; mod-only
```

Guarded by `locals.user.orcid ∈ MODERATOR_ORCIDS` (env list for now).

The `/v1/resolve/work?doi=…` server endpoint currently returns
`501 NOT_IMPLEMENTED` (no DOI reverse index). Either wire a streaming
build of `doi → wid` at server start (cost: one pass over `WorkDois`),
or leave as Phase 2 follow-up — claims store DOI as primary identifier
and don't need server-side DOI resolution today.

---

## 10. Frontend

### 10.1 Components

- Extract `src/lib/components/AuthorLedgerPanel.svelte`. Replaces
  `AuthorOwnerTools.svelte` and absorbs the disown/merge UI from
  `AllWorks.svelte` (the paper-row action triggers still live there, but
  they dispatch through a shared store consumed by the panel).
- `src/lib/components/LedgerEventRow.svelte` — renders one event, polymorphic
  on `kind`, uses `ledger-display.ts` for text.
- `src/lib/components/LedgerStatusBadge.svelte` — `Applied` / `Pending` /
  `Pending review` / `Rejected` / `Skipped` chip with tooltip showing
  reason code.
- `src/lib/components/OrphanEventRow.svelte` (variant of LedgerEventRow)
  — rendered with distinct styling when the subject can't be resolved
  against the current data.
- `src/routes/(stat)/moderate/+page.svelte` — moderator queue.

### 10.2 Layout on `authors/[...]/+page.svelte`

```
[Name header — impact summary]

...

[AllWorks list]

┌── Your Profile Changes ─────────────────────────────────┐
│                                                          │
│  Applied (N)                                             │
│    • Disowned "Foo et al. 2019"        [undo] [change]  │
│    • Merged "Bar 2018" ← "Bar preprint" [undo]          │
│                                                          │
│  Pending — next data refresh (M)                         │
│    • Claim DOI 10.1234/x                 [edit] [×]     │
│        status: Awaiting moderation                       │
│    • Revoke disown "Foo et al. 2019"                [×] │
│    • (Orphan) Disown "Baz 1995"          [edit] [×]     │
│        skipped: oa_id_not_in_dataset                     │
│                                                          │
│  [+ Disown a paper] [+ Claim by DOI]                     │
│  [+ Merge two of my papers] [+ Merge another profile]    │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### 10.3 Editability semantics

- **Pending, non-orphan, `auto_ok`**: `PATCH` or `DELETE` → instant.
- **Pending, `pending_review`**: edit allowed until a moderator decides;
  after `accepted`/`rejected`, the event is frozen (UI hides edit button,
  exposes only "revoke" which creates a counter-event).
- **Applied**: `[undo]` creates a `revoke` counter (pending, `auto_ok`).
  `[change]` creates a `revoke` *and* opens the compose form pre-filled
  for a replacement event.
- **Orphan**: `[edit]` lets the user supply a corrected identifier (e.g.
  paste a different DOI) and re-submit; the orphan itself is revoked and
  a new event replaces it.

### 10.4 Data wiring

`+page.server.ts`:

```ts
const [events, manifest] = await Promise.all([
  LedgerDb.getEventsForOrcid(locals.user.orcid),
  fetch(`${BE_URL}/ledger-status`).then(r => r.json())
]);
const appliedSet = new Set(manifest.applied_event_ids);
const skippedMap = new Map(manifest.skipped.map(s => [s.event_id, s.reason]));

const applied = events.filter(e =>
  appliedSet.has(e.event_id) && e.kind !== 'revoke');
const pending = events.filter(e => !appliedSet.has(e.event_id) && !e.revoked_at);

return { applied, pending, skippedMap, runId: manifest.run_id, … };
```

### 10.5 Reconciling pending counter-events with the paper list

`AllWorks.svelte` needs a `disownedWids` set derived from the *effective*
ledger state, not the raw applied set:

```
effective_disowned = (applied_disowns ∖ applied_disowns_with_pending_revoke)
                   ∪ pending_disowns
```

Plus: "pending revoke of an applied disown" does *not* re-show the paper
in the list — because the paper is no longer in the author's list in the
binary data at all. We simply hide the applied-disown entry's strikethrough
from the panel once the revoke lands. Accept this limitation and surface
it in the tooltip ("Paper will reappear after next data refresh").

Keep this derivation in one utility (`src/lib/utils/ledger-effective.ts`)
not inline in components.

---

## 11. Moderation workflow (streamlined review)

Goal: a moderator can triage claims and author-merges in seconds per item.

### 11.1 Queue page `/moderate`

- Gated by `MODERATOR_ORCIDS` env list.
- One row per `moderation = 'pending_review'` event, ordered oldest first.
- Per row:
  - Submitter (name + ORCID + link to their profile)
  - Kind icon (claim / merge)
  - Subject summary (resolved via `ledger-display.ts`; shows current data
    + display_snapshot fallback)
  - **Quick-accept** / **Quick-reject** buttons (default reason templates)
  - **Inspect** button → drawer with full payload + provenance
    (dm_id_at_creation, run_id_at_creation, ORCIDs on both sides, shared
    coauthors for merge, shared DOIs, etc.)
- Keyboard: `a` = accept, `r` = reject, `j`/`k` = next/prev, `i` = inspect.
- Bulk-accept guarded by a confirm with count.

### 11.2 Auto-hints

To keep review fast, the inspect drawer surfaces pre-computed signals:

- For `merge_authors`: percentage of overlapping coauthors, count of
  matching DOIs, name-similarity score (Levenshtein on display names).
- For `claim_paper`: whether the submitter's ORCID is listed on any
  authorship of the work; whether the work's ORCIDs conflict; whether
  the submitter has authored other papers in the same venue.

These come from small server endpoints (`/v1/mod-hints/:event_id`). Can
be added incrementally in Phase 5.

### 11.3 Decision writes

Accept → `UPDATE ledger_events SET moderation='accepted', moderated_by=?,
moderated_at=datetime('now') WHERE event_id=?`. Also inserts a
`moderation_decision` audit event.

Reject → same, with `moderation='rejected'`.

Once accepted, the event is eligible for the next export snapshot.

---

## 12. Observability & audit

- `applied_manifest.json` includes `applied_event_ids`, `redirected`, and
  `skipped` with reason codes (§6.6).
- `ledger_runs` retains the full manifest JSON for each run — we can
  reconstruct "what did the system look like on date X" forever.
- `/api/ledger-status` exposes manifest + redirect + skip info for the UI.
- `status_dump.sh` to include `$OA_ROOT/user_ledger/applied_manifest.json`
  and the last three manifests.
- Moderator decisions are auditable via `moderation_decision` events in
  `ledger_events`.

---

## 13. Security / abuse mitigations

- API creation of any event requires `locals.user.orcid`; the event is
  always tagged with that ORCID. Users cannot edit another owner's profile.
- Claim authority check (§3.1): if enabled, reject DOIs already bound to a
  different ORCID in the current data.
- Paper-merge authority: submitter must be on at least one side's
  authorship according to current data.
- Author-merge: submitter is automatically the keep side.
- Rate limits per ORCID (§3.3).
- Moderator actions require `ORCID ∈ MODERATOR_ORCIDS`. Environment
  rotated as new moderators are added.
- The Rust pipeline honours no network input. Its only channel is the
  signed snapshot in `$OA_ROOT/user_ledger/`.

---

## 14. Implementation plan — remaining phases

### Phase 5 — Ledger panel UI
1. `AuthorLedgerPanel.svelte` + `LedgerEventRow.svelte` +
   `OrphanEventRow.svelte` + `LedgerStatusBadge.svelte`.
2. `src/lib/utils/ledger-display.ts` (live + snapshot + fallback).
3. `src/lib/utils/ledger-effective.ts` (derived sets for AllWorks).
4. Wire `+page.server.ts` to fetch applied manifest + events, split,
   and pass to the page.
5. Refactor `AllWorks.svelte` to dispatch via a shared store consumed by
   the panel (avoid prop drilling, per CLAUDE.md).
6. Counter-event UX for applied events (`[undo]` / `[change]`).
7. Remove `AuthorOwnerTools.svelte`.
8. Update `docs/details/tree-description.md`.

### Phase 6 — Moderator workflow
1. `src/routes/(stat)/moderate/+page.svelte` + `+page.server.ts`.
2. `src/routes/api/moderation/queue/+server.ts` +
   `src/routes/api/moderation/[event_id]/decide/+server.ts`.
3. `MODERATOR_ORCIDS` env var; auth gate.
4. Keyboard shortcuts, bulk actions.
5. Auto-hint endpoints on `rankless_server` (`/v1/mod-hints/:event_id`).
6. `moderation_decision` audit trail events.

### Phase 7 — Cleanup & docs
1. Delete legacy wrappers (`api/papers/*`, `api/authors/merge-request`).
2. Delete legacy SQLite tables (already handled by migrator; add a final
   no-op migration script for prod).
3. Update `docs/overview.md` architecture diagram to include ledger flow.
4. Delete `AuthorMergeRequest` type from `tree-types.ts` if unreferenced.
5. Document ID-resilience invariants in
   `docs/details/metaprogramming.md` (or a new
   `docs/details/id-resilience.md`).

---

## 15. Validation plan — Phase 4 completion gate

A single comprehensive end-to-end integration test that drives the full
stack (Playwright → SvelteKit dev → SQLite ledger → pipeline → entity
binary → rankless-server → SvelteKit `/api/ledger-status` → Playwright
assertions). Exercises every event kind, every documented skip reason,
and every downstream artefact path. Phase 4 ships only after this is
green.

### 15.1 Test home and orchestration

Two co-operating layers:

1. **Rust fixture builder** — `rankless_rs/tests/ledger_pipeline.rs`
   plus `tests/common/synthetic_oa.rs`. Builds a synthetic OA snapshot
   in a `tempfile::TempDir`, has helpers that run the pipeline
   programmatically (`runner("filter", …)` etc. through
   `derive_links5`), and offers Rust-level assertions against the
   resulting entity binary via `Stowage::get_entity_interface`. This
   layer is *also* runnable on its own as a fast `cargo test` (no
   browser) for the binary-side correctness — see §15.4.

2. **Playwright e2e** — `tests/ledger.spec.ts` (new). Drives the
   user-facing flow: dev-login as a test ORCID, navigate to the
   author page, click disown / merge / claim / revoke, run the
   pipeline as a subprocess (the Rust binary in release mode against
   the same TempDir), reload the page and assert the Applied/Pending
   split via `/api/ledger` and `/api/ledger-status`.

The Playwright spec is the **primary completion gate** because it
exercises the full causal chain end-to-end. The Rust test is a fast
inner loop and a regression net for binary-side invariants that the
UI cannot easily observe.

### 15.2 Fixture (shared between layers)

A helper `tests/common/synthetic_oa.rs` writes the minimal CSV set the
pipeline reads: `authors/main`, `works/main`, `works/authorships`,
`works/biblio`, `works/referenced_works`, `works/topics`,
`works/locations`, `institutions/main`, `sources/main`, `topics/main`,
`subfields/main`, `fields/main`, `domains/main`, `concepts/main`,
plus `entity-csvs/merged-ids/{authors,works}.csv.zst` (one redirect
each, empty otherwise). The Playwright spec invokes it via a small
Rust binary `rankless-rs --bin=fixture-build $TMP` (added in
`rankless_rs/src/bin/fixture_build.rs`) so the TS side stays simple.

### 15.2 Snapshot

Authors:
- A1: orcid `0000-...-1111`, cites=100, works=10 — pinned owner
- A2: orcid `0000-...-2222`, cites=50, works=5 — drop in author merge
- A3: orcid `0000-...-3333`, cites=200, works=20 — keep, same person as A2
- A4: orcid `0000-...-4444`, cites=2, works=1 — pinned, below threshold
- A5: orcid `0000-...-5555`, cites=10000, works=100 — uninvolved control
- A6: orcid `0000-...-6666`, cites=0, works=0 — must be filtered out

Works (with authorships):
- W1, W2 by A1
- W3, W4 by A2
- W5, W6 by A3
- W7, W7b — same paper indexed twice; W7 keep, W7b drop
- W8 by A4 (so the pinned low-cite author has at least one paper)
- W9 by A5

References (citing → cited):
- W5 → W7b   (post-merge resolves to W7)
- W6 → W2    (citation survives even though A1 disowned W2 from her side)
- W9 → W3    (W3's authorship A2→A3 alias-rewritten)

Topics: W7 and W7b each carry a different topic — after merge, W7's
topic set should be the union.

### 15.3 Ledger events in `active.jsonl`

| # | Kind | Outcome |
|---|------|---------|
| 1 | `disown_paper` A1 of W2 | applied (auto_ok) |
| 2 | `merge_authors` keep=A3 drop=A2 | applied (accepted) |
| 3 | `merge_papers` keep=W7 drop=W7b | applied (auto_ok) |
| 4 | `revoke` of an applied disown of W1 (target_inlined) | applied — inverse |
| 5 | `claim_paper` by A1 with DOI `10.1/x` | skipped: `claim_pipeline_not_implemented` |
| 6 | `disown_paper` from an ORCID absent from CSV | skipped: `orcid_not_in_dataset` |
| 7 | `merge_papers` with drop oa_id absent from CSV | skipped: `oa_id_not_in_dataset` |
| 8 | self-merge author A5→A5 | skipped: `missing_oa_id` |
| 9 | chain merge: B→C and A→B in one file | path-compressed to C |
| 10 | malformed JSON line | warning only; other events apply |

Plus `owner_pins.txt`: A1, A4, plus one ORCID absent from CSV (must not
crash, must not show up in `owner_pin_oa_ids`).

In the Playwright flow, **the events are not loaded from a JSON file** —
they are generated by Playwright clicking through the UI and posting via
the existing `/api/papers/disown`, `/api/papers/claim`, `/api/papers/merge`,
`/api/authors/merge-request` endpoints (which all forward to ledger).
The skip-cases that have no UI counterpart (events 5–10 above) are POSTed
via direct `fetch` from inside the Playwright page context. Only the
counterfactual / determinism / merged_ids tests use a file-driven
`active.jsonl` because they need to test the Rust loader's behaviour
without a UI round-trip.

### 15.4 Playwright orchestration

`tests/ledger.spec.ts` — sequential test (`test.describe.serial`). Each
case spins up a fresh TempDir + fresh SQLite. Existing
`playwright.config.ts` already starts SvelteKit; extended to also start
`rankless-server` against the TempDir.

Per-test setup:

1. Build fixture: `cargo run -p rankless-rs --bin fixture-build -- $TMP`
2. First pipeline run (empty ledger): `cargo run --release -p rankless-rs -- filter $TMP && … && derive_links5 $TMP`
3. Start `rankless-server` against `$TMP` on a free port
4. Set env on the SvelteKit web server: `OA_ROOT=$TMP`,
   `RANKLESS_DB_PATH=$TMP/rankless.sqlite`,
   `BE_URL=http://127.0.0.1:$BE_PORT/v1` — done via `webServer.env`
   in `playwright.config.ts` (extend to support per-spec overrides
   via a small fixture helper) or by spawning a dedicated SvelteKit
   instance per spec.

Per-test interactions:

1. Navigate `/dev-login?orcid=0000-…-1111&semanticId=A1&returnTo=/authors/A1`
2. **Disown W2**: click the row's disown button in `AllWorks`. Assert
   POST 200 and the row enters the disowned section in the UI (live
   legacy behaviour; transitions to "Pending" treatment when Phase 5
   ships).
3. **Logout**, log back in as `0000-…-3333` (semanticId A3).
4. **Merge papers W7 ← W7b**: trigger via the same UI handle.
5. **Author-merge** keep=A3, drop=A2: POST to
   `/api/authors/merge-request` directly (the dev UI for this is
   minimal and may not be present yet).
6. **Logout**, log back in as A1, **revoke** the disown of W1 (which
   was applied in a previous run — pre-seed via SQLite insert before
   the spec): POST `/api/ledger/:id/revoke`.
7. **Skipped-cases**: POST events 5–10 directly to `/api/ledger`.
8. Verify `/api/ledger?orcid=…` returns the expected per-user event
   list with `revoked_at` properly set.

Pipeline re-run + reload:

1. Stop rankless-server.
2. Re-export the ledger:
   `uv run -m pyscripts.export_user_ledger $TMP --db $TMP/rankless.sqlite`.
3. Re-run pipeline (`filter` → `derive_links5`).
4. Restart rankless-server.
5. In Playwright: `await page.goto('/api/ledger-status')` and assert
   the JSON shape: applied_event_ids contains 1, 2, 3, 4; skipped
   contains the documented reason codes; redirected[] contains the
   `merged_ids` rewrite for the deprecated → canonical id; run_id
   matches snapshot_manifest.

### 15.5 Assertions — filter + a1 + a2 (Rust layer)

- `Authors` dm-space contains exactly {A1, A3, A4, A5}; A2 gone (drop),
  A6 gone (filter)
- A4 in `Authors` despite cites=2 < `MIN_AUTHOR_CITE_COUNT`
- `Works` dm-space contains everything except W7b
- `LoadedIdMap<Authors>`: lookup of A2_oa returns A3's dm_id
- `LoadedIdMap<Works>`: lookup of W7b_oa returns W7's dm_id
- Authorship A1↔W2 absent (disowned)
- Authorship A1↔W1 present (revoke counter restored the edge)
- Authorships for W3, W4 indexed under A3's dm_id
- W7's authors = union of W7 + W7b authorships, deduped
- `raw_cites[A3_dm] == 250`, `raw_works[A3_dm] == 25`
- `names[A3_dm] == "A3"`, `orcids[A3_dm] == 0000-…-3333`
- DOI / title / year for W7_dm sourced from W7 (not W7b)
- `work-references` for W5_dm contains W7_dm (W7b alias resolved)
- `work-topics` for W7_dm contains both W7's and W7b's topics
- `a1_manifest.json`: applied = [event 2, 3]; skipped contains
  expected reason codes from events 7, 8; run_id ≡ snapshot_manifest
- `applied_manifest.json`: applied = [1, 2, 3, 4]; skipped contains
  events 5, 6, 7, 8 with documented reasons; run_id ≡ a1's

### 15.6 Assertions — full pipeline (through `derive_links5`, Rust layer)

- coauthor network of A3 contains A2's coauthors (via dm_id remap)
- KD-tree over peers builds without panic; A4 (pinned, low-cite)
  embeds without `-inf` (uses `.max(1)` on cites)
- hit_papers count for A3 reflects merged citations from W3, W4
- subfield-citation arrays for A3 sum the contributions from A2's
  papers and A3's papers

### 15.7 Assertions — UI-visible (Playwright layer)

- After login, the author page loads and disown/merge/claim controls
  are interactable.
- Disowned paper row disappears from the active section in `AllWorks`
  (legacy behaviour) before the pipeline runs.
- After the pipeline re-run and reload, `/api/ledger-status` reflects
  the event split: 4 applied, the documented skipped reasons,
  one redirect.
- `/api/ledger?orcid=…` returns the same set; revoked events have
  non-null `revoked_at`.
- Logging in as a low-cite ORCID (A4) and visiting `/authors/A4`
  returns 200 and shows the profile (proves owner-pin made it
  through the filter).
- Logging in as an ORCID absent from CSV pins it but visiting their
  (non-existent) profile returns 404 — pinning does not synthesise
  authors.

### 15.8 Counterfactual + determinism (Rust layer)

- **Counterfactual**: same fixture, empty `active.jsonl` and
  `owner_pins.txt`. Assert: A4 dropped (no pin), A2 keeps own dm_id
  (no merge), `raw_cites[A3_dm] == 200`, no manifest entries.
- **Determinism**: same fixture, run pipeline twice. Assert byte-equal
  outputs for every entity file. Catches any non-deterministic order
  dependency in the writers.

### 15.9 Stress / regression cases (Rust layer)

- Author alias chain (event 9) resolves to C after path compression.
- Manifest run_id mismatch between a1 and a2: drop and re-export
  ledger between steps; a2 must panic with the documented message.
- Revoke whose `target_inlined` references an unknown event kind:
  silently no-op, no panic.
- `merged_ids` redirect: include `entity-csvs/merged-ids/authors.csv.zst`
  with `(stale_oa, current_oa)`; an event whose primary `oa_id` is
  `stale_oa` resolves to `current_oa`. Manifest's `redirected[]`
  records the rewrite.

### 15.10 Pre-test sanity (already passing)

- `cargo test -p rankless-rs path_compress`, `normalize_orcid`
- `bun test src/lib/server/ledger-hash.test.ts`,
  `src/lib/server/id_resolver.test.ts`

### 15.11 What's deliberately NOT covered

- Moderator queue (Phase 6) — separate Playwright spec when Phase 6 lands
- AuthorLedgerPanel-specific assertions (Phase 5) — extend
  `tests/ledger.spec.ts` when the panel ships

---

## 16. Deferred follow-ups (not in this plan)

- **`merged_ids` population** in `to-csv` step: extend `csv_writers.rs`
  to parse OpenAlex `merged_ids/` tables and emit
  `entity-csvs/merged-ids/{authors,works}.csv.zst` using `MergedIdRow`.
  (Loaders and consumer-side wiring land in Phase 4 finalisation.)
- `add_paper_request` full implementation (synthetic-CSV injection,
  synthetic OA id allocation, moderation UI).
- `claim_paper` full pipeline effect (currently skipped with
  `claim_pipeline_not_implemented`).
- `/v1/resolve/work?doi=…` server-side DOI resolution (currently 501).
- E-mail notifications on Applied transitions.
- Cross-owner conflict resolution UI.
- Per-event dry-run ("what will change in your numbers") — requires a
  lightweight in-server diff tool.
- Historical rollback (replay `ledger_runs.manifest_json` to reconstruct
  a prior state).
