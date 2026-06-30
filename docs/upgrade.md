# Upgrade plan

Remaining improvement work, ordered by priority. When an item lands, **delete it from this
file** (progress is tracked via git). Pipeline-parallelism work is already planned in
`docs/todo-backend.md` — not duplicated here.

---

## 1. Performance

### Rust — serving & cache creation

- **Respond before finishing all-period cache writes** —
  `rankless_trees/src/part_iterator.rs::fill_calculate`: the default-period (pid 0) tree is
  folded last, so a first-time query waits for prune + wide-prune + two zstd writes of _every_
  other period before its response is set (`write_resp` runs inline per period). Move the
  `cache_tree` calls for non-requested periods onto a background writer (channel + one writer
  thread receiving `(tree, path)`); the worker thread then only prunes, and disk/zstd work
  overlaps folding. Cuts both first-view latency and wall time of warm-up cache generation.
- **Tree-cache cold start (`big_prep`/`big_read`)** — `read_big_calculate` pushes records into
  a `MinHeap` one `read_exact` at a time; read whole year-files into a buffer and bulk-build
  the heap (`Vec` + `into()` heapify is O(n) vs O(n log n) pushes).
- **`/resolve/work?oa_id=` is O(N_works)** —
  `rankless_server/src/handlers/search.rs::resolve_work_get` linear-scans `gets.work_oa`.
  Build a sorted permutation index (`Box<[u32]>` over work ids, sorted by oa_id; 4 B × N) at
  startup and binary-search it. Only the ledger flow hits this today, but it's a public route
  — a scripted client can pin a worker thread with it.
- **Static JSON endpoints clone per request** — `util.rs::static_router` stores the
  serialized JSON as `Arc<str>` but `state_get` does `.to_string()` per hit and serves it as
  `text/plain`. Store `axum::body::Bytes` (cheap refcount clone) and set
  `content-type: application/json` explicitly.
- **Confirm compression in front of `/v1`** — tree/works responses are large JSON; verify the
  nginx forward (3039→3038) gzips them, else add `tower-http` `CompressionLayer`. Measure
  before adding the dependency.

### Svelte — bundle & runtime

- **Replace cytoscape+fcose with a small custom force layout** — the only consumer is the
  ≤25-node co-author graph (`network-force.ts`, now a lazy 566 kB vendor chunk). A ~60-line
  Fruchterman–Reingold loop removes two runtime deps, the chunk, and the
  `chunkSizeWarningLimit` bump in `vite.config.ts`. Verify visually against current layouts.
- **`AuthorNetwork.svelte` edge rendering is O(n²) in markup** — nested
  `{#each Array(n)}…{#each Array(n)}` with `getWeight` called up to 4× per pair on every
  reactive pass. Precompute a `$: edges = …` list of `{i, j, w}` once and iterate that.

## 2. Bugs & footguns

- **`MAX_FIXBUF` write/read asymmetry** (`dmove`, see `docs/metaprog-bugs.md`): writes are
  heap-unbounded but `BackendLoading::load_backend` reads into `[u8; MAX_FIXBUF]`. Add a
  post-monomorphization compile-time guard (associated `const OK: () = assert!(E::BYTE_SIZE
<= MAX_FIXBUF)` referenced in `load_backend`) so oversized fixed attributes fail at build,
  not at startup.
- **In-memory tree-cache races** (`part_iterator.rs::Progress::from_e` / `fill_calculate`):
  the `Done`-but-missing-period path returns `Calculate` _without_ re-marking the entry
  `InProgress` (concurrent identical queries duplicate the computation), and the final
  `insert` overwrites whatever is there — waiters are only notified on the
  was-`InProgress` path. Restructure: always swap in `InProgress` before calculating, and
  merge new pids into an existing `Done` set.
- **Two id spaces, one naming convention** — `NameState.semantic_id_map` maps to **dm_id**
  while `oa_id_map` maps to **response index**; every handler must remember which is which
  (`sem_id_get` uses both correctly, but only by care). Rename (`sem_to_dm`, `oa_to_rid`) or
  wrap in newtypes (`DmId(u32)` / `Rid(u32)`).
- **`parse_semantic_id` only handles uppercase `%2F`** (`util.rs`) — lowercase `%2f` (or any
  other double-encoded char) slips through. Do one real percent-decode pass at this boundary
  and document why double-decoding is needed at all.
- **Vestigial expand-control wiring in `FullQc.svelte`** — `expandControlInd` is declared and
  threaded into `updateLevelSpecs` but never assigned (eslint's
  `no-immutable-reactive-statements` caught it; line 92 is now a `const`). Either delete the
  parameter end-to-end or wire up whatever was supposed to set it.
- **`radialWeightedLayout` is dead and wrong** (`network-util.ts`) — unused (commented out of
  the layout map) and its flat index (`i * n + j - 1`) doesn't match `getIndex`'s triangular
  encoding. Delete it.

## 3. Developer ergonomics

- **Structured logging** — the server/tree layer logs via bare `println!` (21 call sites): no
  timestamps, no levels, no request correlation, which makes `journalctl` archaeology painful.
  Adopt `tracing` + `tracing-subscriber` (mature, zero-cost when filtered) and a
  `tower_http::trace::TraceLayer` on the router; convert `tlog`/`log` in `part_iterator.rs`
  into spans so per-query timings nest under one request span.
- **DRY the handler resolution chain** — `view_get`, `stats_get`, `peers_get`, `works_get`,
  `tree_get` each re-implement etype → `NameState` → psid → dm_id → rid with slightly
  different early-outs. Extract one
  `fn resolve_entity<'a>(states, etype, sem_id) -> Option<(&'a NameState, usize /*dm*/, usize /*rid*/)>`
  in `util.rs`.
- **`make mega_test` traceability** — orchestration exists (`pyscripts/mega_test.py`), but a
  failed run leaves evidence scattered. Per run: write `logs/mega-test/{timestamp}/` holding
  the dev-server log, a backend `journalctl` slice for the run window, the make-step outputs,
  and Playwright traces (`trace: 'retain-on-failure'` in `playwright.ledger.config.ts`); print
  a phase-timing summary at the end so regressions in pipeline-step duration are visible.
  The Rust-side fixture/pipeline invariants tests are tracked in `docs/todo-backend.md`
  (integration test gate) — building those makes mega_test failures attributable to a layer.
- **Dead-parameter cleanup in `rankless_trees/src/io.rs`** — `get_tids_of_dir(_, true, _)` is
  always called with `defalt_to_all = true`, so the directory-scanning branch is dead (and the
  name is a typo). Inline the live branch; same file has stale `use std::{u32, u8, vec}`
  imports.
