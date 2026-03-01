# Codebase Reference

Quick reference for navigating the Rankless codebase. Covers Rust crates, Svelte frontend, and Python scripts.

---

## Rust Crates

### rankless_rs — Data Processing Pipeline

CLI tool that ingests OpenAlex/Scopus CSV dumps and produces binary data files consumed by the server. Uses `dmove`/`dmove_macro` to metaprogram Rust source tailored to the dataset's shape.

**Steps (run in order via `mods_as_comms!` in `lib.rs`):**

| File | Role |
|------|------|
| `src/lib.rs` | Module root; exports public API; dispatches pipeline steps |
| `src/main.rs` | CLI entry; reads `OA_ROOT` env; calls `lib::runner()` |
| `src/common.rs` | `Stowage` (file/data manager), marker traits, type aliases, parsing utils |
| `src/env_consts.rs` | Config constants: year ranges, thresholds |
| `src/data_consts.rs` | Dataset-level lookup tables |
| `src/oa_structs.rs` | OpenAlex JSON schema structs (Work, Author, Institution, …) |
| `src/semantic_ids.rs` | Semantic ID generation for frontend URL slugs |
| `src/agg_tree.rs` | Hierarchical aggregation tree construction |
| `src/filter.rs` | Entity filtering |
| `src/csv_writers.rs` | CSV output for validation |
| `src/biblo_var_att.rs` | Variable-length bibliographic attribute handling |
| `src/steps/a1_entity_mapping.rs` | Parse CSVs; deduplicate and map entity IDs for Works/Authors/Institutions/Sources/Topics/Countries; year filtering |
| `src/steps/a2_init_atts.rs` | Initialize attributes: DOIs, ORCIDs, bibliographic info, topics, locations; Levenshtein-based author name dedup; Nobel laureate category (u8 per author, 0=none, 1=Physics, 2=Chemistry, 3=Medicine, 4=Economics) from `authors/nobel.csv.gz` |
| `src/steps/derive_links1.rs` | work→subfields, work→institutions, work→countries |
| `src/steps/derive_links2.rs` | work→sources; top source per work |
| `src/steps/derive_links3.rs` | Coauthor networks; hit papers (highly-cited in entity domain) |
| `src/steps/derive_links4.rs` | Per-entity hit-paper sorted lists; author citing-hit sets (direct + once-removed, top-50 by composite score: cite count, source prestige, distance); Nobel laureate direct connections boosted by `NOBEL_MULTIPLIER` to bias their top-50 toward directly-cited hit papers |
| `src/steps/derive_links5.rs` | Institutional relationships; era records; top-15 author stats |
| `src/gen/` | Generated Rust source (entity/attribute/link definitions); do not edit manually |

---

### rankless_trees — Tree Query Library

Hierarchical tree data structures and query logic. Provides `Getters` interface for tree traversal; used directly by the server.

| File | Role |
|------|------|
| `src/interfacing.rs` | Core `Getters` struct; loads data interfaces; tree traversal; `make_interfaces!` macro setup |
| `src/io.rs` | `TreeRunManager` (threaded query execution), `CacheKey`/`CacheValue`, `TreeResponse`, attribute label management; `WT = ET<Works>` alias |
| `src/path_finder.rs` | Citation path graph traversal; `RefGraph` trait; `author_to_work_paths()` |
| `src/ids.rs` | ID encoding/decoding; `AttributeLabelUnion` for heterogeneous entity IDs |
| `src/extensions.rs` | Extension methods for tree traversal |
| `src/instances.rs` | Concrete tree instances and test configs |
| `src/part_iterator.rs` | Incremental tree iteration; `TreeMakingParams` |
| `src/prune.rs` | Tree result pruning |
| `src/arr_ext.rs` | Array manipulation extensions |
| `src/test_utils.rs` | Test utilities (`#[cfg(test)]`) |

**Key patterns:** `BeS<M, E>` (Backend Selector) for flexible data loading; condition-variable-based thread pool in `TreeRunManager`.

---

### rankless_server — HTTP API Server

Axum server on port 3038. Loads pre-processed binary data; answers tree queries, search, and spec requests.

| File | Role |
|------|------|
| `src/main.rs` | Routes: `/v1/query`, `/v1/search`, `/v1/specs`, geo-coord endpoint; initializes `Getters` for Authors/Institutions/Subfields/Countries/Sources/HitPapers; pre-computed cache (`CACHEABLE_FROM=10k`); mimalloc allocator; KD-tree for institution geo |
| `src/consts.rs` | `MAX_HITS=80`, `PORT=3038`, `SEARCH_SIZE=20`, `MAX_SLICE=40k`, `N_THREADS=16` |

---

### Supporting Crates

| Crate | Role |
|-------|------|
| `dmove` / `dmove_macro` | Metaprogramming: generates entity/attribute/link Rust source tailored to dataset shape; see `docs/metaprogramming-make.md` |
| `muwo_search` | Custom partial-string search engine for scholarly entity names |

---

## Svelte Frontend (`src/`)

SvelteKit app; SSR via `+page.server.ts` files; all visualizations are hand-written SVG (Cytoscape.js the only viz dependency).

### Types & Constants

| File | Role |
|------|------|
| `lib/tree-types.ts` | `TreeGen<T>`, `View`, `Paper`, `RelatedEntity`, `SearchResult`, `TreeResponse`, `BreakdownSpec`, `RootType`, `EntityType`, `InstRel` |
| `lib/constants.ts` | `BE_URL`, `ENTITY_TYPES`, `MAX_LEVEL_COUNT=4`, `DEFAULT_LIMIT_N=10`, `COMPLETE_YEAR=1950`, ORCID endpoints |
| `lib/types.ts` | `SurveySubmit`, `SurveyRecord` |

### Utility Modules

| File | Role |
|------|------|
| `lib/tree-functions.ts` | Tree traversal, flattening, filtering; `getDefaultBreakdowns()`, `getBreakdownOptions()` |
| `lib/tree-events.ts` | Click/hover/selection handlers |
| `lib/visual-util.ts` | `rescale()`, `getSankeyPath()`, `pinRange()` |
| `lib/metric-calculation.ts` | Specialization scores, impact metrics |
| `lib/network-util.ts` | Co-authorship graph utilities |
| `lib/route-functions.ts` | URL builders |
| `lib/loading-functions.ts` | Data fetching orchestration |
| `lib/text-format-util.ts` | Number/text formatting |
| `lib/style-util.ts` | CSS/SVG styling |
| `lib/stores.ts` | Svelte reactive stores |
| `lib/sitemap-functions.ts` | SEO sitemap helpers |

### Routes

| Route | Role |
|-------|------|
| `(stat)/` | Home page; top entity lists |
| `(stat)/[rootType]/[...semanticId]/` | Entity hero page (tree + network + map) |
| `(stat)/author-papers/[...semanticId]/` | Author paper profile: standout papers, citation impact DAG with sub-graph nav, all works with pagination, disown/claim (owner only), export controls |
| `(stat)/about/` | About page |
| `(stat)/survey/` | User survey |
| `(stat)/login/`, `logout/`, `callback/` | ORCID OAuth flow (login accepts `returnTo` for post-auth redirect) |
| `api/papers/helpers.ts` | Shared `authedPaperAction` helper for paper API endpoints |
| `api/papers/disown/` | POST/DELETE: disown/undo-disown a paper (authenticated) |
| `api/papers/claim/` | POST/DELETE: claim/unclaim a paper by DOI (authenticated) |
| `tiles/[rootType]/[...semanticId]/` | Treemap visualization |
| `path-to-paper/[aId]/[...workId]/` | Citation path finder: author → paper |
| `path-to-person/[aidSrc]/[aidTarget]/` | Collaboration path finder: author → author |
| `oa-id/[oaId]/` | OpenAlex ID → entity redirect |
| `api/survey/` | Survey submission endpoint |
| `pic/[rootType]/[...semanticId]/breakdown.svg/` | Dynamic breakdown SVG |
| `sitemap*.xml/`, `robots.txt/` | SEO |

### Key Components

| Component | Role |
|-----------|------|
| `TreeSvg.svelte` | Main hierarchical breakdown tree (SVG) |
| `ConceptMap.svelte` | Research space field-to-field network |
| `AuthorNetwork.svelte` | Co-authorship network (Cytoscape layout) |
| `WorldMapSvg.svelte` | Geographical citation impact map |
| `TileTreeMap.svelte` | Treemap alternative view |
| `PaperRainbow.svelte` | Hit paper citation area chart with scrollable list |
| `ImpactDag.svelte` | Citation impact DAG: connected-component decomposition with sub-graph navigation, three-layer layout (citing/intermediate/authored), collapsed mid-layer, expand/collapse, SVG bezier edges, swipe + keyboard nav |
| `DagChip.svelte` | Individual paper chip for ImpactDag: title, year, badges (standout/prestigious/nobel), expandable details |
| `AllWorks.svelte` | Paginated author paper list with client-side fetch, disown/undo UI (owner only) |
| `ExportControls.svelte` | Sort, filter, citation style, BibTeX copy/download controls for paper lists |
| `WorkElem.svelte` | Single paper display |
| `SearchResults.svelte` | Search autocomplete results |
| `ScrollyGraph.svelte` / `ScrollySank.svelte` | Scrollytelling visualizations |
| `TimelineViz.svelte` | Year-based timeline |
| `PathLevelInfoBox.svelte` / `MidpathBar.svelte` | Citation/collaboration path UI |
| `HeadControl.svelte` | Navigation header |

### Server Utilities

| File | Role |
|------|------|
| `lib/server/session.ts` | ORCID session management; `setSession` accepts `redirectTo` param |
| `lib/server/db.ts` | SQLite singleton (better-sqlite3, WAL mode); `PaperDb` interface for disowned/claimed papers |
| `lib/utils/reference-format.ts` | Academic reference formatting (HTML/APA/MLA/Chicago, BibTeX with unique keys) |
| `lib/utils/paper-helpers.ts` | Paper/author/source name resolution from entityAtts; highlight detection (standout/prestigious) |
| `lib/utils/dag-builder.ts` | DAG construction from RefTree; directional subgraph pairing (2 citing papers per group); layer classification |
| `lib/utils/impact-summary.ts` | Computes summary counts (Nobel, Science/Nature, standout) for citing papers |
| `lib/utils/clipboard-download.ts` | Clipboard copy and file download helpers |
| `lib/utils/nobel.ts` | Fetches Nobel laureate OA IDs from S3 JSON; caches in localStorage (1-week TTL) |
| `hooks.server.ts` | SvelteKit middleware |

---

## Python Scripts (`pyscripts/`)

| File | Role |
|------|------|
| `cache_prompting.py` | Pre-warms server cache; identifies high-citation entities needing special handling |
| `bm.py` | Benchmark suite: spawns Rust backend, measures latency/throughput/memory |
| `deploy.py` | Automates EC2 deployment: Nginx, systemd, SSL (Let's Encrypt), code push |
| `live_monitoring.py` | Health monitoring: response-time checks (<1.2s), distributed alert swarm, email alerts |
| `log_parsing.py` | Parses Nginx access logs for hourly performance reports |
| `report.py` | Report generation from benchmark data |
| `make_test_dataset.py` | Generates mini/micro/nano data subsets for CI |
| `lib_data_generation.py` | Test data generation utilities |
| `extend_csvs.py` | CSV transformation utilities: source area-fields, source quartiles (qs), author wiki-slugs, Nobel laureate categories (`authors/nobel.csv.gz` from `extern/nobel-matches.csv`) |
| `sitemap_validation.py` | Validates generated sitemaps |
| `survey_result_export.py` | Exports survey responses |
| `alpha_test.py` | Alpha-release test utilities |
| `nobel.py` | Nobel laureate data utilities |
| `start_comparison.py` | Starts Flask+Rust comparison backends |
| `svg_export.py` | Exports visualizations as SVG |
| `sql_comparison_eval.py` | SQL vs Rust correctness/benchmark comparisons (see sql-yardstick/) |

---

## Data Flow

```
OpenAlex CSV dumps
  → rankless_rs steps (a1→a2→links1-6)
  → binary data files + generated Rust source (src/gen/)
      → rankless_trees (Getters, TreeRunManager)
          → rankless_server (Axum, port 3038)
              → SvelteKit SSR (+page.server.ts)
                  → Svelte components (SVG rendering)
```

Entity hero page request: SvelteKit calls `/v1/query` → server looks up entity by semantic ID → `Getters` traverses tree → `TreeRunManager` builds `TreeResponse` (tree + papers + related entities + yearly stats) → frontend renders `TreeSvg`, `ConceptMap`, `WorldMapSvg`.

---

## Entity Types

`authors`, `institutions`, `sources` (journals), `countries`, `subfields`, `hit-papers`

Discipline hierarchy: `domains (4)` → `fields (26)` → `subfields (252)` → `topics (4516)` (ASJC-based)

Each entity has *production* (own papers) and *impact* (papers citing those) sets.
