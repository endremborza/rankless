# Rankless — Architecture & Reference

**Rankless** is an interactive scholarly data explorer for real-time browsing of large
citation networks: low-latency exploration of millions of citation relationships across
papers, authors, institutions, journals, countries, and research disciplines.

Pipeline shape: **OpenAlex CSVs → binary pipeline (`rankless_rs`) → Axum server
(`rankless_server`) → SvelteKit frontend (`src/`)**.

Contents:
1. [Overview](#overview) — data, visualizations, layers
2. [Codebase reference](#codebase-reference) — file-by-file index
3. [Data flow](#data-flow)
4. [Schema](#schema)
5. [Breakdown selection (UI mechanism)](#breakdown-selection)
6. [Metaprogramming & make pipeline](#metaprogramming--make-pipeline)
7. [Parallelization](#parallelization)
8. [Local development](#local-development)

---

## Overview

### Data

Source: OpenAlex (primary) + SCImago/Scopus (journal rankings).

Six entity types: **Papers, Authors, Institutions, Sources** (journals), **Countries,
Disciplines**. Discipline hierarchy: Domains (4) → Fields (26) → Subfields (252) →
Topics (4516), ASJC-based.

Core relationships: citations, authorships, topical classifications. Affiliations link
institutions to authorships (author↔paper pairs). Each searchable entity has a hero page
built around **production** (its papers) and **impact** (papers citing those).

The full production dataset contains ~80M works; subset sizes (nano/micro/mini) are used
for local dev, CI, and correctness/scale validation.

### Visualizations

- **Hierarchical Tree** — interactive breakdown of production/impact across topical,
  geographic, and institutional dimensions; configurable breakdown per level; surfaces
  most-cited paper per branch.
- **Research Space** — field-to-field network based on author co-occurrence.
- **Collaborator Network** — co-authorship graph scoped to an author's frequent collaborators.
- **Geographical Impact Map** — citation flows by country, optionally colored by
  specialization vs. baseline.
- **Peers** — comparison of an entity against its closest peers (coordinate proximity +
  subfield similarity); subfield citation heatmap, decade sparkline, totals.
- **Hit Paper Breakdown** — lazy-loaded citation breakdown for individual standout papers
  (TileTreeMap of citing entities), inline in PaperRainbow or on `/hit-papers/{semId}`.

### Layers

**Processing (`rankless_rs`):** ingests OpenAlex/Scopus CSV dumps through an ordered
step pipeline (entity mapping → attribute init → link derivation 1–5). Uses
`dmove`/`dmove_macro` metaprogramming to generate Rust source tailored to the dataset,
producing optimized binary data files. See [Metaprogramming](#metaprogramming--make-pipeline).

**Backend (`rankless_server`):** Axum HTTP server (port 3038) over pre-processed binary
data. Custom partial-string search (`muwo_search`). Proactive cache pre-warming
(`pyscripts/cache_prompting.py`) for high-traffic entities. Peers endpoint pre-loads peer
ID arrays and memory-maps per-subfield citation counts at startup.

**Tree library (`rankless_trees`):** hierarchical query engine with thread pool
(`TreeRunManager`), citation path finder (`path_finder.rs`), in-memory caching.

**Frontend (`src/`):** SvelteKit/Svelte with SSR. All visualizations hand-written SVG;
Cytoscape.js the only external viz dependency. ORCID authentication on author profile
pages. SQLite (better-sqlite3, WAL mode) backs an append-only **user ledger** of
profile modifications (disown/claim/merge); see [the ledger to-do](todo-backend.md) for
remaining moderator + cleanup work.

**Deployment (`pyscripts/deploy.py`):** Linux, systemd (Rust backend + Bun frontend),
Nginx reverse proxy, Let's Encrypt SSL. Live monitoring via distributed alert swarm
(`live_monitoring.py`).

---

## Codebase reference

### rankless_rs — data processing pipeline

CLI tool that ingests OpenAlex/Scopus CSV dumps and produces binary data files consumed by
the server. Steps run in order via `mods_as_comms!` in `lib.rs`:
`a1_entity_mapping → a2_init_atts → derive_links1 → … → derive_links5`.

| File | Role |
|------|------|
| `src/lib.rs` | Module root; exports public API; dispatches pipeline steps |
| `src/main.rs` | CLI entry; reads `OA_ROOT` env; calls `lib::runner()` |
| `src/common.rs` | `Stowage` (file/data manager), marker traits, `reverse_id`, type aliases, `MmapBox`, parsing utils |
| `src/csv_iter.rs` | Parallel CSV partition reader `ObjIter<T>`; one thread per partition file, prefetch into a sync channel |
| `src/env_consts.rs` | Config constants: year ranges, thresholds (driven by `RANKLESS_ENV`) |
| `src/data_consts.rs` | Dataset-level lookup tables |
| `src/oa_structs.rs` | OpenAlex JSON schema structs |
| `src/semantic_ids.rs` | Semantic ID generation for frontend URL slugs |
| `src/agg_tree.rs` | Hierarchical aggregation tree construction |
| `src/filter.rs` | Entity filtering (alias-aware counting + owner-pin filter from the ledger) |
| `src/csv_writers.rs` | CSV output for validation |
| `src/biblo_var_att.rs` | Variable-length bibliographic attribute handling |
| `src/peers.rs` | KD-tree peer finding: `PartitionedTrees`, `Embed<D>`, `GenericPeerCtx`; log-PCA embedding, distance primitives |
| `src/user_ledger.rs` | Loads + resolves the user ledger snapshot (stable OA id → BigId → dm_id); applies aliases/disowns/owner-pins; writes `applied_manifest.json` |
| `src/steps/a1_entity_mapping.rs` | Parse CSVs; dedup + map entity IDs; year filtering; ledger drop-side skips |
| `src/steps/a2_init_atts.rs` | Init attributes (DOIs, ORCIDs, biblio, topics, locations); Levenshtein name dedup; Nobel category; ledger alias/merge application |
| `src/steps/derive_links1.rs` | work→subfields, work→institutions, work→countries |
| `src/steps/derive_links2.rs` | work→sources; top source per work; per-subfield citation arrays |
| `src/steps/derive_links3.rs` | Coauthor networks; hit papers; page filter + semantic IDs; unified peer discovery via `PeerConfig` |
| `src/steps/derive_links4.rs` | Per-entity hit-paper sorted lists; author citing-hit sets; hit paper semantic IDs + peers |
| `src/steps/derive_links5.rs` | Era records (yearly citations, top journals/authors/subfields) for hit papers |
| `src/gen/` | Generated Rust source — **do not edit manually** |

### rankless_trees — tree query library

| File | Role |
|------|------|
| `src/interfacing.rs` | `Getters` struct; loads data interfaces; `make_interfaces!` macro; `RootInterfaces` (sem_ids, peers, hit_sem_ids, hit_dois) |
| `src/io.rs` | `TreeRunManager` (threaded execution), `CacheKey`/`CacheValue`, `TreeResponse`, attribute labels |
| `src/path_finder.rs` | Citation path graph traversal; `RefGraph`; `author_to_work_paths()` |
| `src/ids.rs` | ID encoding/decoding; `AttributeLabelUnion` |
| `src/extensions.rs` | Extension methods for tree traversal |
| `src/instances.rs` | Concrete tree instances and test configs |
| `src/part_iterator.rs` | Incremental tree iteration; `TreeMakingParams` |
| `src/components.rs` | Tree components (`DisJ`, `IntX`, `PostRefIterWrap`, `CountryInstsPost`); `StackBasis` folding |
| `src/prune.rs` | Tree result pruning |
| `src/arr_ext.rs` | Array manipulation extensions |
| `src/test_utils.rs` | Test utilities (`#[cfg(test)]`) |

Key patterns: `BeS<M, E>` (Backend Selector) for flexible data loading; condvar-based
thread pool in `TreeRunManager`.

### rankless_server — HTTP API server

| File | Role |
|------|------|
| `src/main.rs` | Routes (`/v1/query`, `/v1/search`, `/v1/specs`, `/v1/peers/:etype/:semid`, `/v1/ladder/:etype`, `/v1/ledger-status`); init `Getters`; load `PeerAux`; pre-computed cache (`CACHEABLE_FROM=10k`); mimalloc |
| `src/consts.rs` | `MAX_HITS=80`, `PORT=3038`, `SEARCH_SIZE=20`, `MAX_SLICE=40k`, `N_THREADS=16` |

### Supporting crates

| Crate | Role |
|-------|------|
| `dmove` / `dmove_macro` | Metaprogramming: generates entity/attribute/link Rust source tailored to dataset shape (see [Metaprogramming](#metaprogramming--make-pipeline)) |
| `muwo_search` | Partial-string search engine for entity names: `lib.rs` (trie/engine), `io.rs` (serialization), `fixed_heap.rs`, `merging.rs`, `tests.rs` |

### Svelte frontend (`src/`)

SvelteKit app; SSR via `+page.server.ts`; all visualizations hand-written SVG (Cytoscape.js
the only viz dependency).

**Types & constants**

| File | Role |
|------|------|
| `lib/tree-types.ts` | `TreeGen<T>`, `View`, `Paper`, `RelatedEntity`, `SearchResult`, `TreeResponse`, `BreakdownSpec`, `RootType`, `EntityType`, `InstRel` |
| `lib/constants.ts` | `BE_URL`, `ENTITY_TYPES`, `MAX_LEVEL_COUNT=4`, `DEFAULT_LIMIT_N=10`, `COMPLETE_YEAR=1950`, ORCID endpoints |
| `lib/v_constants.ts` | `VERSION`, `LAST_MOD` build-time info |
| `lib/types.ts` | `SurveySubmit`, `SurveyRecord` |

**Utility modules**

| File | Role |
|------|------|
| `lib/tree-functions.ts` | Tree traversal/flattening/filtering; `getDefaultBreakdowns()`, `getBreakdownOptions()` |
| `lib/tree-events.ts` | Click/hover/selection handlers |
| `lib/visual-util.ts` | `rescale()`, `getSankeyPath()`, `pinRange()` |
| `lib/metric-calculation.ts` | Specialization scores, impact metrics |
| `lib/network-util.ts` | Co-authorship graph utilities |
| `lib/route-functions.ts` | URL builders |
| `lib/loading-functions.ts` | Data fetching orchestration |
| `lib/text-format-util.ts` | Number/text formatting; `semantify` + `SEM_MAP` (see [breakdown selection](#breakdown-selection)) |
| `lib/style-util.ts` | CSS/SVG styling |
| `lib/stores.ts` | Svelte reactive stores |
| `lib/sitemap-functions.ts` | SEO sitemap helpers |
| `lib/util.ts` | General utilities |
| `lib/utils/ledger-effective.ts` | Derives effective disowned/ledger sets for `AllWorks` from applied + pending events |

**Routes**

| Route | Role |
|-------|------|
| `(stat)/` | Home; top entity lists |
| `(stat)/[rootType]/[...semanticId]/` | Entity hero page (tree + network + map; ledger panel for owners) |
| `(stat)/[rootType]/table/` | Sortable/searchable entity stats table |
| `(stat)/about/`, `(stat)/survey/` | About / survey |
| `(stat)/login/`, `(stat)/logout/`, `callback/`, `dev-login/` | ORCID OAuth + dev bypass |
| `api/ledger/`, `api/ledger/[event_id]/`, `api/ledger/[event_id]/revoke/`, `api/ledger-status/` | Ledger CRUD + status |
| `api/papers/{disown,claim,merge}/`, `api/authors/merge-request/` | Legacy paper/author actions (forward to ledger; slated for removal) |
| `tiles/[rootType]/[...semanticId]/` | Treemap visualization |
| `path-to-person/[aidSrc]/[aidTarget]/` | Collaboration path finder |
| `oa-id/[oaId]/` | OpenAlex ID → entity redirect |
| `api/survey/`, `pic/.../breakdown.svg/`, `sitemap*.xml/`, `robots.txt/` | Survey / dynamic SVG / SEO |

**Key components**

| Component | Role |
|-----------|------|
| `TreeSvg.svelte` | Main hierarchical breakdown tree |
| `ConceptMap.svelte` | Research-space field network |
| `AuthorNetwork.svelte` | Co-authorship network (Cytoscape) |
| `WorldMapSvg.svelte` | Geographical citation impact map |
| `TileTreeMap.svelte` | Treemap view |
| `PaperRainbow.svelte` | Hit-paper citation area chart with scrollable list |
| `HitPaperBreakdown.svelte` | Lazy citation breakdown for a single hit paper |
| `ImpactDag.svelte` / `DagChip.svelte` | Citation impact DAG + paper chips |
| `AllWorks.svelte` | Paginated author paper list; ledger/disown UI |
| `AuthorLedgerPanel.svelte` | Owner's profile-changes panel (applied/pending events) |
| `AuthorOwnerTools.svelte` | Legacy owner action UI (slated for removal) |
| `ExportControls.svelte` | Sort/filter/citation-style/BibTeX controls |
| `Peers.svelte` / `BarChart.svelte` | Peer comparison bars + shared span-bar chart |
| `WorkElem.svelte`, `SearchResults.svelte` | Single paper / search autocomplete |
| `ScrollyGraph.svelte` / `ScrollySank.svelte` / `TimelineViz.svelte` | Scrollytelling + timeline viz |
| `PathLevelInfoBox.svelte` / `MidpathBar.svelte` | Path UI |
| `HeadControl.svelte`, `Toc.svelte`, `FlatOutFrame.svelte` | Header / sticky nav / flat-view frame |

**Server utilities**

| File | Role |
|------|------|
| `lib/server/session.ts` | ORCID session management |
| `lib/server/db.ts` | SQLite singleton (better-sqlite3, WAL); ledger tables |
| `lib/server/id_resolver.ts` | Resolves UI entity refs to stable-ID payload blocks |
| `lib/server/ledger-hash.ts` | `subject_hash` computation for ledger dedup |
| `lib/utils/reference-format.ts` | Academic reference formatting (APA/MLA/Chicago, BibTeX) |
| `lib/utils/paper-helpers.ts` | Paper/author/source name resolution; highlight detection |
| `lib/utils/dag-builder.ts` | DAG construction from RefTree |
| `lib/utils/impact-summary.ts` | Summary counts (Nobel, Science/Nature, standout) for citing papers |
| `lib/utils/clipboard-download.ts` | Clipboard copy + file download |
| `hooks.server.ts` | SvelteKit middleware |

### Python scripts (`pyscripts/`)

| File | Role |
|------|------|
| `cache_prompting.py` | Query infrastructure: `BatchRequester`, `get_specs_and_ys`, `get_resdf`, URL gen; `addr` configurable |
| `server_ops.py` | `ServerProcess`, `DockerServer`, `build_server()`, `current_branch()`, `checkout()` |
| `stow_ops.py` | `StowManager` (rsync stash per branch), `RebuildLevel` |
| `bm.py` | Benchmark suite: latency/throughput/memory across branches |
| `branch_comparison.py` | Branch-to-branch structural diff + timing (see [benchmarking](benchmarking.md)) |
| `sql_comparison.py` | Flask/PostgreSQL vs Rust diff + benchmark; two Docker containers |
| `tree_diff.py` | Structural diff primitives: `flatten_tree`, `make_diff_df`, `metric_stats`, `top_source_stats` |
| `comparison_report.py` | Shared report generation: `CompResult`, summary/grouped DFs, plots, md/HTML |
| `export_user_ledger.py` | Exports SQLite ledger → `$OA_ROOT/user_ledger/` snapshot before `filter` |
| `deploy.py` | EC2 deployment: Nginx, systemd, SSL, code push |
| `live_monitoring.py` | Health monitoring + email alerts |
| `log_parsing.py`, `report.py` | Nginx log parsing + hourly performance reports |
| `make_test_dataset.py`, `lib_data_generation.py` | nano/micro/mini subset generation |
| `extend_csvs.py` | CSV transforms: source area-fields, quartiles, author wiki-slugs, Nobel categories |
| `sitemap_validation.py`, `survey_result_export.py`, `nobel.py`, `svg_export.py` | Sitemap / survey / Nobel / SVG export utilities |

---

## Data flow

```
OpenAlex CSV dumps
  → rankless_rs steps (a1→a2→links1-5)
  → binary data files + generated Rust source (src/gen/)
      → rankless_trees (Getters, TreeRunManager)
          → rankless_server (Axum, port 3038)
              → SvelteKit SSR (+page.server.ts)
                  → Svelte components (SVG rendering)
```

Entity hero page request: SvelteKit calls `/v1/query` → server looks up entity by semantic
ID → `Getters` traverses tree → `TreeRunManager` builds `TreeResponse` (tree + papers +
related entities + yearly stats) → frontend renders `TreeSvg`, `ConceptMap`, `WorldMapSvg`.

**Entity types:** `authors`, `institutions`, `sources` (journals), `countries`,
`subfields`, `hit-papers`. Each entity has *production* (own papers) and *impact* (papers
citing those) sets.

---

## Schema

OpenAlex-derived relational shape the pipeline reads from:

```mermaid
erDiagram
  "fields" {
    BIGINT id PK
    TEXT display_name
    BIGINT domain FK
  }
  "domains" {
    BIGINT id PK
    TEXT display_name
  }
  "works" {
    BIGINT id PK
    TEXT doi
    TEXT title
    TEXT display_name
    BIGINT publication_year
    TEXT type
  }
  "works-authorships" {
    BIGINT parent_id FK
    BIGINT author FK
    BIGINT institution FK
  }
  "authors" {
    BIGINT id PK
    TEXT orcid
    TEXT display_name
  }
  "institutions" {
    BIGINT id PK
    TEXT display_name
    TEXT country_code
    TEXT display_name_acronyms
  }
  "subfields" {
    BIGINT id PK
    TEXT display_name
    BIGINT field FK
  }
  "works-locations" {
    BIGINT parent_id FK
    BIGINT source FK
  }
  "sources" {
    BIGINT id PK
    TEXT display_name
  }
  "works-referenced_works" {
    BIGINT parent_id FK
    BIGINT referenced_work_id FK
  }
  "works-topics" {
    BIGINT parent_id FK
    BIGINT id
    DOUBLE PRECISION score
  }
  "topics" {
    BIGINT id PK
    TEXT display_name
    BIGINT subfield FK
    BIGINT field FK
    BIGINT domain FK
  }
  "fields" ||--|{ "domains" : "domain -> id"
  "works-authorships" ||--|{ "works" : "parent_id -> id"
  "works-authorships" ||--|{ "institutions" : "institution -> id"
  "works-authorships" ||--|{ "authors" : "author -> id"
  "subfields" ||--|{ "fields" : "field -> id"
  "works-locations" ||--|{ "works" : "parent_id -> id"
  "works-locations" ||--|{ "sources" : "source -> id"
  "works-referenced_works" ||--|{ "works" : "parent_id -> id; referenced_work_id -> id"
  "works-topics" ||--|{ "works" : "parent_id -> id"
  "topics" ||--|{ "subfields" : "subfield -> id"
  "topics" ||--|{ "fields" : "field -> id"
  "topics" ||--|{ "domains" : "domain -> id"
```

---

## Breakdown selection

How users explore an entity's impact/production hierarchically (`FullQc.svelte`):

- **`breakdownOptions`** — tree of breakdown dimensions loaded from the backend (not
  hardcoded); each node is a dimension (e.g. "by country") with optional children.
- **`selectedBreakdowns`** — array storing the user's current selection path.
- **`updateLevelSpecs`** — traverses `breakdownOptions` by `selectedBreakdowns` to prepare
  `levelOptions` for the next level. `MidpathBar` renders the available options.
- **Dynamic tree loading** — `updateTreeSpecId` detects when a selection requires a
  different `treeId`; `loadNewQc` fetches that tree from the backend.
- **Semantic descriptions** — `semantify` (in `text-format-util.ts`) maps raw option
  identifiers to human-readable text via the hierarchical `SEM_MAP`, context-aware on the
  selection path (e.g. `"countries-false"` → `"are cited by authors working in"`).

---

## Metaprogramming & make pipeline

Each pipeline step in `rankless_rs/src/steps/` is **both** a data processor and a code
emitter. When run, a step processes OpenAlex CSV data and writes a corresponding `.rs` file
into `rankless_rs/src/gen/` containing dataset-specific entity/attribute/link definitions
required by subsequent steps and the server. Each step's generated file becomes a
compile-time dependency for the next step.

### `dmove_macro` — two roles

**`src/lib.rs` — proc-macro library**: macros used in the steps —
`#[derive_meta_trait]` (generates a `*TraitMeta` struct whose `meta()` returns the Rust
source string for a trait impl emitted into gen/), `def_me_struct!` / `def_srecs!` /
`impl_subs!` / `impl_fbarrs!` / `impl_stack_basees!` (tree-folding, byte-serialization,
stack-basis boilerplate), `#[derive_tree_getter]`.

**`src/main.rs` — orchestration binary (`dmove-macro`)**: drives the build pipeline; knows
nothing about entity definitions. Built via `cargo build --release -p dmove-macro`.

### Orchestration commands

- **`make-setup [--fast]`** — reads `steps/` to discover step names, writes a `Makefile`
  (or `Makefile.fast`). Each target is a gen file with the previous gen file as a
  dependency, giving correct incremental ordering.
- **`pre-build -s <step>`** — modifies source so the crate compiles as if only steps up to
  (and including) `<step>` exist: rewrites `lib.rs` `mods_as_comms!`, `steps/mod.rs` (`pub
  mod` up to `<step>`), and `gen/mod.rs` (all *previously completed* gen files, not the
  current one).
- **`post-run -s <step>`** — adds the newly generated file to `gen/mod.rs`.

### Makefile structure

Both Makefiles suppress `dead_code`/`unused` via RUSTFLAGS (early steps leave later
symbols unreferenced). Each target:

```makefile
rankless_rs/src/gen/derive_links3.rs: rankless_rs/src/steps/derive_links3.rs rankless_rs/src/gen/derive_links2.rs
	./target/release/dmove-macro -p rankless_rs pre-build -s derive_links3
	RUSTFLAGS="-C target-cpu=native -A dead_code -A unused" cargo build -p rankless-rs --profile gen-release
	RUSTFLAGS="-C target-cpu=native -A dead_code -A unused" cargo run -p rankless-rs --profile gen-release -- derive_links3
	./target/release/dmove-macro -p rankless_rs post-run -s derive_links3
```

`RUSTFLAGS` is set explicitly because env RUSTFLAGS overrides `.cargo/config.toml` rather
than appending; `target-cpu=native` is re-declared so it isn't dropped. Touching a step
file (or its gen dependency) re-triggers only that step and downstream ones.

### Bootstrap constraint

When step X compiles, `gen/mod.rs` includes only through step X−1, so step X **cannot** use
trait impls from `gen/X.rs`. Any call requiring an impl in `gen/X.rs` must not appear in
`steps/X.rs`:
- `declare_iter::<…>()` — safe in same step (generates the impl)
- `get_marked_interface::<E, M, Be>()` — requires `E: MarkedAttribute<M>`; only safe if that
  impl is in gen/(X−1) or earlier
- `ditf::<Marker, E, T>()` — requires only `E: Entity`; safe in same step
- Types defined in `gen/X.rs` cannot be imported in `steps/X.rs`

If step X must write data for a type it creates, move those writes to step X+1.

### Fast (debug) pipeline

The `gen-release` profile (`codegen-units=1`, `lto=true`, `opt-level=3`) makes each compile
slow. For iterating on step logic — where only the generated `.rs` matters, not runtime
speed — use `gen-debug` (inherits `dev`):

```sh
./target/release/dmove-macro -p rankless_rs make-setup --fast
make -f rankless_rs/Makefile.fast                                   # full pipeline
make -f rankless_rs/Makefile.fast rankless_rs/src/gen/derive_links3.rs   # single step
```

Fast targets use `RUSTFLAGS="-A dead_code -A unused" cargo … --profile gen-debug` and omit
`target-cpu=native` (negligible at `opt-level=0`).

---

## Parallelization

Core primitives live in `dmove/src/para.rs`, re-exported from `dmove`. No rayon — custom
threading for precise control.

- **`Worker<T>`** — batch work queue. `para` / `para_n` create a `crossbeam_channel::bounded`
  queue, spawn N scoped threads (receive loops), stream items, send `None` sentinels, join.
  Used in `a2_init_atts.rs` (CSV ingestion) and `derive_links3.rs` (`PeerWorker`).
- **`par_join!`** — fork-join for heterogeneous closures; spawns each expression as a scoped
  thread, joins all. Used in `derive_links2.rs` (five `CiteDeriver` methods).
- **`para_multi_gen_run!`** — one thread per type parameter:
  `para_multi_gen_run!(fn, TypeA, TypeB; arc_arg)`. Used in `derive_links3::main` (work_count
  for 6 entity types) and server startup.
- **`AcTuple<T>` + condvar helpers** — `Arc<(Mutex<T>, Condvar)>` one-shot result
  notification (`set_and_notify` / `wait_for_data*`). Used in `rankless_trees/src/io.rs`.

**Interface loading** — `make_interface_struct!` (in `rankless_rs/src/common.rs`) generates a
struct whose fields load in parallel threads at construction. Two forms: 4-category
`(IT, e…; f…; v…; m…)` and 5-category `(IT, e…; f…; v…; loc…; m…)` (adds
`Arc<Locators<E>>` via `get_locator`). `rankless_trees/src/interfacing.rs` calls the
5-category form via `make_interfaces!`.

| Module | Mechanism | Parallelized work |
|---|---|---|
| `rankless_rs/steps/a2_init_atts.rs` | `Worker<T>::para()` | CSV rows: works, biblios, authorship |
| `rankless_rs/steps/a1_entity_mapping.rs` | `std::thread::spawn` + `Vec<JoinHandle>` | Independent entity ID mapping |
| `rankless_rs/steps/derive_links2.rs` | `par_join!` | 5 `CiteDeriver` methods |
| `rankless_rs/steps/derive_links3.rs` | `para_multi_gen_run!` + `Worker<T>::para()` | Work counts per entity; peer selection |
| `rankless_rs/src/common.rs` | `make_interface_struct!` | Parallel data loading at server startup |
| `rankless_trees/src/io.rs` | Persistent pool (`VecDeque` + `Condvar`) | Tree query serving; 16 threads |
| `rankless_server/src/main.rs` | `para_multi_gen_run!` + Tokio (16 workers) | Entity state init; HTTP handling |

`TreeRunManager` is intentionally a persistent pool (long-lived workers share mmapped data),
not `Worker<T>` (one-shot batch).

---

## Local development

For collaborators who want a running Rankless without the full pipeline or an OpenAlex
snapshot.

**Prerequisites:** macOS or Linux, Git. macOS: Xcode CLT + Homebrew. Everything else (Rust,
uv, Bun, zstd) is checked by `make bootstrap`.

**One-time setup:**

```sh
git clone git@github.com:endremborza/rankless.git
cd rankless
make bootstrap
```

This: (1) clones `ccl-science-data` into `~/.cache/rankless/` and regenerates its reader
bindings; (2) `uv sync` + `bun install`; (3) downloads the nano snapshot (~100 MB) into
`./data/nano-snapshot/`; (4) runs the pipeline (`RANKLESS_ENV=nano`) → `./data/nano-root/`
(~10 min first time); (5) builds `rankless-server` (`RANKLESS_ENV=nano` so compile-time
constants match the data). Idempotent — stamp files at `.ready` / `.pipeline-done` skip
finished steps.

**Daily flow:**

```sh
make dev            # backend 127.0.0.1:3038 + SvelteKit 127.0.0.1:5173, interleaved logs
uv run -m pyscripts.dev.run --open   # auto-launch browser
```

**Where things live:** `data/nano-snapshot/` (downloaded JSON, gitignored),
`data/nano-root/` (local pipeline output, gitignored), `libs/ccl-science-data` (symlink →
`~/.cache/rankless/ccl-science-data`; override with `CCL_CLONE_DIR=<path>`),
`target/release/rankless-server`, `.env` (gitignored, seeded from `.env.example`).

**Troubleshooting:**

| Symptom | Fix |
|---|---|
| `port 3038/5173 already in use` | `lsof -nP -iTCP:3038 -sTCP:LISTEN` to find the other instance |
| `backend never became ready` | inspect `make dev` output; usually incomplete OA_ROOT — re-run `make bootstrap` |
| `NANO_ARTIFACT_URL` 404 | the artifact host isn't reachable; get a fresh URL |
| ccl-science-data import error | `rm -rf libs/ccl-science-data && make bootstrap` |

**Maintainer — refreshing / testing the snapshot artifact:** the artifact is just the
filtered raw JSON snapshot (no pipeline output, no binaries). Prereq:
`$OA_TEST_ROOT/nano-snapshot/` (build once with `uv run -m pyscripts.make_test_dataset`).

```sh
uv run -m pyscripts.dev.build_nano_artifact     # tars + zstds the snapshot, prints SHA-256 + URL lines
python -m http.server 8000                      # serve it
make test-dev-env                               # full bootstrap in a clean Ubuntu container, verifies serve
NANO_ARTIFACT_URL=http://10.0.0.5:9000/nano-root.tar.zst make test-dev-env   # override host
```

`make test-dev-env` uses `--network=host` (Linux); macOS hosts would swap the URL for
`host.docker.internal:8000`.
