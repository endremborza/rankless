# To-do — Backend, pipeline & API

Remaining work on the Rust pipeline, server, and data-side features. When a section lands,
**delete it from this file** (progress is tracked via git, not crossed-out bullets).

Sections:

- [Pipeline parallelism](#pipeline-parallelism)
- [Institution peer quality](#institution-peer-quality)
- [Author profile ledger — remaining](#author-profile-ledger--remaining)
- [MCP server](#mcp-server)

---

## Pipeline parallelism

Spots where additional parallelism could cut pipeline step wall time.

### `derive_links1` — parallel `InvertedMultiLink` construction

`main` builds three inverted link structures sequentially (`WorkReferences`, `WorkTopics`,
`WorkSources`). Each `from_stowage` is read-only and produces an independent in-memory
`Box<[Box<[…]>]>`. Run the three _build_ phases concurrently with `std::thread::scope`
(the `par_join!` macro returns no values, so `thread::scope` is the right primitive); keep
the subsequent `stow_as_work_link` writes sequential. Expected ~3× for this phase.

```rust
let (wr, wt, ws) = std::thread::scope(|s| {
    let h1 = s.spawn(|| InvertedMultiLink::<WorkReferences>::from_stowage(&stowage));
    let h2 = s.spawn(|| InvertedMultiLink::<WorkTopics>::from_stowage(&stowage));
    let h3 = s.spawn(|| InvertedMultiLink::<WorkSources>::from_stowage(&stowage));
    (h1.join().unwrap(), h2.join().unwrap(), h3.join().unwrap())
});
```

### `derive_links3` — parallel benchmark computations

After `para_multi_gen_run!(work_count, …)`, three benchmark maps compute sequentially.
`compute_year_bms` and `compute_sf_bms` are fully independent; `compute_sf_year_bms` depends
on `year_bms` only. Two-phase: (1) `thread::scope` runs year_bms ∥ sf_bms; (2)
sf_year_bms. Halves this preparatory phase's wall time.

### `derive_links3` — parallel `entity_coords_filter!` calls

Five coord-filter invocations run sequentially after hit-paper selection. The first four
(Institutions, Subfields, Countries, Sources) are independent and can move into a `par_join!`
block; Authors must stay separate (feeds `compute_author_peers`). Constraint: `ditf` calls
`declare_iter`, which writes to stowage via internal locking — safe to parallelize if
`Stowage` write methods are mutex-protected (they appear to be, per `Arc` usage elsewhere).

### `derive_links5` — parallel `write_all_sem_ids`

Five sequential writes (Authors, Institutions, Sources, Subfields typed + Countries inline).
Each reads a separate entity's CSVs (IO-bound) and writes a disjoint semantic-id attribute.
The four typed calls are ideal for `para_multi_gen_run!`; Countries runs after. Likely the
most impactful step since CSV reading dominates and the files don't overlap.

### `derive_links4` — sharded author hit-paper accumulation

The O(H × R × A) loop filling `direct[author]` / `once_removed[author]` is single-threaded.
The write target is indexed by author id → **shard-by-author** is lock-free: partition the
author ID space into T ranges; each thread iterates all hit papers but writes only its range
(all reads — `wor_refs`, `w2a`, `parc` — are immutable slices); no merge step. The final
`.zip().map().unzip()` is per-author too, partition by the same ranges.

---

## Institution peer quality

University peers come out weak. Code: `rankless_rs/src/peers.rs` (embedding, partitioned
KD-tree, distance primitives), `rankless_rs/src/steps/derive_links3/peer_ctx.rs`
(`InstPeerCtx`, `W_PEER_*` weights, `final_distance_calc`), call site
`derive_links3/mod.rs` (`order_basis = inst_wcounts`), signal source
`derive_links2.rs` (`CitSubfieldsArrayMarker`).

### Why it's weak

Peers derive from **one signal**: `CitSubfieldsArrayMarker` (`[u32; 253]` per institution —
the subfields of works that _cite_ it; an impact profile). Three-stage pipeline: log-PCA
embedding → work-count-partitioned KD-tree candidate search (10 buckets, query sees its
bucket ±1, `K_TREE=500` neighbors) → re-rank top 10 by a weighted sum:

```
1.0*sf_log_dist + 0.5*sf_rate_dist + 0.3*geo_sq_dist + 0.5*country
```

Failure modes:

1. **Incommensurate scales.** Terms are summed un-normalized; `geo_sq_dist` (raw squared
   lat/lon degrees: hundreds within a continent, 8000+ across) dominates → ranking becomes
   "nearest on the map." `sf_rate_dist` (~0.05–0.15) and `country` (0/1) never move the
   order. (Explains Corvinus → matched to Budapest neighbors, not other business schools.)
2. **Size double-counted.** Log-count PC1 ≈ size; the candidate set is _also_ size-bucketed.
   Field-mix axes get little weight.
3. **Only the citing-field histogram.** No co-citation, direct inter-institution citation,
   or co-authorship — the signals that define genuine peers.
4. **Sparse profiles for small institutions** → noisy neighbors exactly where peer quality
   matters most.
5. **Asymmetry / hard partition edges.** `final_distance_calc` scores only on a's top-10
   subfields; `PartitionedTrees::query` can't see perfect peers two buckets away.

### Improvements (by impact/effort)

- **A. Normalize re-rank terms before weighting** _(cheap, high impact)_ — replace
  `geo_sq_dist` with haversine squashed to [0,1] (`1 − exp(−d/d₀)`, d₀ ~few hundred km);
  z-score/min-max each term over the candidate set, or hand-tune against observed magnitudes.
- **B. Decouple size from field mix** _(cheap–medium)_ — embed from field _proportions_
  (`count/total`, optionally CLR-transformed) not raw log counts; keep size strictly as the
  partition key; consider widening/overlapping the ±1 bucket window.
- **C. Co-citation / shared-reference signal** _(medium, highest ceiling)_ — bibliographic
  coupling via cosine of outgoing `RefSubfieldsArrayMarker` (already exists); and/or
  inter-institution direct-citation counts. Even folding `RefSubfieldsArrayMarker` in
  (what the institution _studies_) sharpens specialised universities.
- **D. Symmetrise the field distance** _(cheap)_ — score on the union of a's and b's top
  subfields, or a symmetric divergence (cosine / Jensen–Shannon over the full histogram).
- **E. Make peer quality measurable** _(supporting)_ — hand-label a few obvious peer sets
  (business schools, technical universities, …), report precision@10 so changes can be
  compared rather than eyeballed.

**First step:** do A + B together (both localized to `peers.rs`/`peer_ctx.rs`, need only a
`derive_links3` re-run), evaluate with E before reaching for C.

---

## Author profile ledger — remaining

Append-only, ORCID-authenticated ledger of profile edits (disown / claim / merge papers,
merge authors) applied early in the pipeline so all downstream artefacts reflect them.
**Phases 1–4 (SQLite `ledger_events` table, stable-ID resolution, pipeline ingest in
`filter`/`a1`/`a2`, `applied_manifest.json`, server `/v1/ledger-status`, CRUD API) and most
of Phase 5 (`AuthorLedgerPanel.svelte`, `ledger-effective.ts`, wired into the author page)
are committed.**

### Standing constraints for remaining work

- **Moderation defaults:** `disown_paper`/`merge_papers` → `auto_ok`; `merge_authors`/
  `claim_paper` → `pending_review`. `revoke` counter-events inherit `auto_ok`.
- **Applied events are immutable** — UI "edit" of an applied event creates a new pending
  `revoke` counter-event (+ optional replacement). The log grows monotonically.
- **Payloads store stable IDs only** (OA id primary; DOI/ORCID fallbacks; dm_id/semantic_id
  stored as provenance, never used for resolution). Resolution: oa_id → merged_ids redirect
  (removed, see deferred) → DOI (works) / ORCID (authors).
- **Owner pinning** is a distinct filter stage: any ORCID that logs in is pinned into the
  keep-filter (via `owner_pins.txt`) so they can always manage their profile.
- **Pipeline concurrency:** no write lock during runs; snapshot taken at start, later writes
  are pending after the run.

### Phase 5 — finish the ledger panel

- `src/lib/utils/ledger-display.ts` — pure function for per-subject text: live lookup →
  `display_snapshot` fallback ("as of run X") → raw id ("No longer in data"). Unit-testable
  against a synthetic `paperMap`.
- Counter-event UX in `AuthorLedgerPanel`: `[undo]` (creates `revoke`, `auto_ok`) and
  `[change]` (revoke + pre-filled compose form) for applied events; orphan `[edit]`
  (revoke + replacement with corrected identifier).
- Optional sub-component extraction (`LedgerEventRow`, `OrphanEventRow`, `LedgerStatusBadge`)
  for DRY rows/badges.
- Remove `AuthorOwnerTools.svelte` once the panel fully replaces it.

### Phase 6 — moderator workflow

- `src/routes/(stat)/moderate/+page.svelte` + `+page.server.ts` — queue of
  `moderation='pending_review'` events, oldest first; per row: submitter, kind, resolved
  subject summary, quick-accept/reject, inspect drawer. Keyboard `a`/`r`/`j`/`k`/`i`;
  bulk-accept behind a count confirm.
- `src/routes/api/moderation/queue/+server.ts` +
  `src/routes/api/moderation/[event_id]/decide/+server.ts`, gated by
  `locals.user.orcid ∈ MODERATOR_ORCIDS` (env list).
- Decisions: `UPDATE ledger_events SET moderation=…, moderated_by=…, moderated_at=…` plus a
  `moderation_decision` audit event. Accepted events become eligible for the next export.
- Auto-hints (incremental): `/v1/mod-hints/:event_id` — for `merge_authors`, % overlapping
  coauthors, matching DOIs, name similarity; for `claim_paper`, whether submitter ORCID is on
  any authorship, ORCID conflicts, same-venue history.

### Phase 7 — cleanup

- Delete legacy wrappers: `src/routes/api/papers/*`, `src/routes/api/authors/merge-request`.
- Drop legacy SQLite tables (`disowned_papers`, `claimed_papers`, `paper_merges`,
  `author_merge_requests`) — final no-op migration for prod.
- Delete `AuthorMergeRequest` type from `tree-types.ts` if unreferenced.
- Update `docs/architecture.md` to mark the ledger flow as the sole path (remove the legacy
  route row and `AuthorOwnerTools`).

### Integration test gate

A Playwright e2e (`tests/ledger.spec.ts`, exists) is the primary gate; a fast Rust inner
loop covers binary-side invariants. Still to build:

- `rankless_rs/src/bin/fixture_build.rs` — writes a synthetic minimal OA snapshot to a
  TempDir so the TS side can invoke `cargo run -p rankless-rs --bin fixture-build -- $TMP`.
- `rankless_rs/tests/ledger_pipeline.rs` (+ `tests/common/synthetic_oa.rs`) — runs the
  pipeline programmatically and asserts binary-side invariants: drop/keep author & work
  dm-space membership, alias rewrites in references/authorships, merged topic unions,
  summed cites/works, owner-pin survival, `a1_manifest`/`applied_manifest` applied/skipped
  sets, counterfactual (empty ledger), and byte-equal determinism across two runs.
- Playwright path: per-test fresh TempDir + SQLite; first run with empty ledger, click
  disown/merge/claim/revoke through the UI (skip-only cases POSTed directly), re-export
  (`pyscripts.export_user_ledger`), re-run pipeline, restart server, assert
  `/api/ledger-status` split (4 applied + documented skip reasons) and `/api/ledger`
  `revoked_at`. Already-green unit tests: `path_compress`, `normalize_orcid`,
  `ledger-hash.test.ts`.

### Deferred follow-ups

- **`merged_ids` redirect** — removed (the CSV writer was never implemented, so it was a
  permanent no-op). The pipeline now `eprintln!`s a warning if an oa_id stops resolving.
  Re-implement only if events start failing with `oa_id_not_in_dataset` due to OpenAlex ID
  deprecation: parse OpenAlex `merged_ids/` in `csv_writers.rs` → emit
  `entity-csvs/merged-ids/{authors,works}.csv.zst`; restore `merged_ids.rs` loader +
  `apply_redirect`; re-add `redirected[]` to `applied_manifest.json`.
- **`claim_paper` pipeline effect** — currently skipped with
  `claim_pipeline_not_implemented` (display-only). Needs authorship-row synthesis: which
  `Authorships` id to assign, whether to update `inst` relations.
- **`add_paper_request`** — schema reserved only; needs synthetic-CSV injection + OA-id
  allocation + moderation UI.
- **`/v1/resolve/work?doi=…`** — returns 501 (no DOI reverse index); wire a streaming
  `doi → wid` build at server start, or leave (claims store DOI as primary id).
- E-mail notifications on Applied transitions; cross-owner conflict resolution UI; per-event
  dry-run ("what changes in your numbers"); historical rollback via `ledger_runs.manifest_json`.

---

## MCP server

Wrap the existing low-latency binary backend in MCP so any MCP-compatible agent can consume
citation data without bespoke integration. **Nothing is built yet** (`mcp_server/` does not
exist). Separate process (Python, `mcp` SDK + `httpx`) proxying to `rankless_server` on
localhost:3038 — MCP SDKs are mature in Python/TS not Rust, response shaping is simpler in a
scripting language, and rate-limiting/task logic shouldn't sit in the data hot path.

### Phase 1 — MVP (no backend changes)

`mcp_server/` (uv-managed) with `server.py`, `tools.py`, `resources.py`, `prompts.py`,
`client.py` (async HTTP to Rust), `response_shaping.py` (flatten trees, add URLs). stdio
transport for local Claude Desktop / claude-code.

Six core tools wrapping existing endpoints:
| Tool | Maps to |
|------|---------|
| `search_entities(query, entity_type)` | `/v1/names/:etype?q=` |
| `get_entity_profile(entity_type, semantic_id)` | `/v1/views/:etype/:id` |
| `get_citation_tree(entity_type, semantic_id, year?, depth?)` | `/v1/trees/:root/:id` (flattened in MCP) |
| `get_papers(entity_type, semantic_id, offset?, limit?)` | `/v1/works/:etype/:id/:from` |
| `get_author_peers(semantic_id)` | `/v1/author-peers/:asem` |
| `lookup_by_orcid(orcid)` | `/v1/orcid/:id` |

Two resources (`rankless://schema/entity-types`, `rankless://schema/discipline-hierarchy`),
one prompt (`author_impact_report`). Every response carries a `rankless_url` backlink. Demo:
"Tell me about David Baker's research impact."

### Phase 2 — paper search & stats (needs backend work)

- **Paper/keyword search** (most impactful): index paper titles in `muwo_search` (papers are
  loaded as `WorksNames`; add a `NameState` for papers). ~930k papers is ~4–5× the largest
  current index (authors ~211k) — benchmark the trie. Expose `/v1/search-papers?q=&year_from=
&year_to=&subfield=`. Stretch: inverted title-token index for boolean keyword queries.
- **`/v1/stats/:etype/:semantic_id`** → `{ papers, citations, top_subfields, year_range }`
  from coordinates + `WorkCountMarker` + subfield citation array (already computed, just not
  exposed flat).
- **DOI lookup** `/v1/doi/:doi` — `WorkDois` + a startup hash map (DOI → work dm_id).
- MCP tools `search_papers`, `get_entity_stats`, `lookup_by_doi`; SSE transport; IP-based
  rate limiting (no keys yet).

### Phase 3 — batch, paths, remote

- `POST /v1/batch` dispatcher over existing handlers (cuts round-trips for bibliographies).
- Tools: `find_citation_path`, `find_collaboration_path` (path pages), `compare_entities`
  (`/v1/shallows`), `get_field_landscape`, `batch_lookup`.
- Deploy alongside web server; HTTP+SSE with CORS.
- Optional `?format=flat|summary` query param on tree endpoints for agent-friendly output.

### Phase 4+ — "work-for-us" exchange & analytics (aspirational)

Agents earn elevated API access by doing in-context tasks (name disambiguation, affiliation
resolution, topic classification, …) validated via gold tasks (20% known answers) + consensus
(3+ agreeing). `request_elevated_access` / `submit_task_results`; API-key issuance + rate
tiers (anon 100/min, keyed 1000/min); reputation + audit log. Then query-pattern analytics,
coverage-gap reports, agent-tuned cache, workflow-derived prompts.
