# Rankless — Architecture & Reference

**Rankless** is an interactive scholarly data explorer for real-time browsing of large
citation networks: low-latency exploration of millions of citation relationships across
papers, authors, institutions, journals, countries, and research disciplines.

Pipeline shape: **OpenAlex CSVs → binary pipeline (`rankless_rs`) → Axum server
(`rankless_server`) → SvelteKit frontend (`src/`)**.

Companion references: `benchmarking.md` (comparison/bench tooling + results), `reporting.md`
(traffic/perf site), `tree-internals.md` (tree-construction internals), `topic-tags.md` (topic
creator/dominator tags), `sharecard-render-test.md` (OG share-card test), `v2-to-v3-changes.md`
(v2→v3 changelog), `unfinished-features.md` (built-but-hidden features).

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

What counts as a paper: OpenAlex work types `article`, `conference-paper`, `book-chapter`, `book` and `review`, not retracted, published within the covered years. Conference papers arrive under three of those labels — society proceedings (IEEE, ACM) have always been `article`, while proceedings series (LNCS and kin) are typed `book-chapter` in older snapshots and `conference-paper` once OpenAlex retypes them — so all three stay whitelisted regardless of snapshot vintage. Works of any type also enter when forced: a pinned owner's œuvre and claim-resolved works ride through the type and citation screens (`rankless_rs/src/filter.rs`).

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
ID arrays and memory-maps per-subfield citation counts at startup. The per-entity hero
relations (top authors/fields/journals/topics/countries) are memory-mapped top-N tables
rebuilt into the response on demand per entity view, rather than held resident.

**Tree library (`rankless_trees`):** hierarchical query engine with thread pool
(`TreeRunManager`), citation path finder (`path_finder.rs`), in-memory caching.

**Frontend (`src/`):** SvelteKit/Svelte with SSR. All visualizations hand-written SVG;
Cytoscape.js the only external viz dependency. ORCID authentication on author profile
pages. SQLite (better-sqlite3, WAL mode) backs an append-only **user ledger** of
profile modifications (disown/claim/merge), plus its review layer: a
`subject_enrichment` cache of external metadata (Crossref/OpenAlex/ORCID) and
AI `review_verdicts`, both surfaced on the `/admin/ledger` moderation queue
(see [ledger-review.md](ledger-review.md)).

**Deployment (`pyscripts/recalc.py` → `deploy.py`):** staged recalc + deploy flow
(`uv run -m pyscripts recalc <stage>` for the data, `uv run -m pyscripts deploy
<action>` for the application, see [deploy](deploy.md)). Linux, systemd `--user`
services rendered from the `deploy/` unit templates — locally by
`pyscripts/services.py` (`make setup-services`, profiles dev / small-alpha / live /
worker), remotely by `pyscripts/deploy.py` (EC2: Nginx reverse proxy, Let's Encrypt
SSL, code push). Live monitoring via distributed alert swarm (`live_monitoring.py`).

---

## Codebase reference

### rankless_rs — data processing pipeline

CLI tool that ingests OpenAlex/Scopus CSV dumps and produces binary data files consumed by
the server. Steps run in order via `mods_as_comms!` in `lib.rs`:
`a1_entity_mapping → a2_init_atts → derive_links1 → … → derive_links5`.

| File                             | Role                                                                                                                                                                                                                                    |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/lib.rs`                     | Module root; exports public API; dispatches pipeline steps                                                                                                                                                                              |
| `src/main.rs`                    | CLI entry; reads `OA_ROOT` env; calls `lib::runner()`                                                                                                                                                                                   |
| `src/common.rs`                  | `Stowage` (file/data manager), marker traits, `reverse_id`, type aliases, `MmapBox`, parsing utils                                                                                                                                      |
| `src/csv_iter.rs`                | Parallel CSV partition reader `ObjIter<T>`; one thread per partition file, prefetch into a sync channel                                                                                                                                 |
| `src/env_consts.rs`              | Config constants: year ranges, thresholds (driven by `RANKLESS_ENV`)                                                                                                                                                                    |
| `src/data_consts.rs`             | Dataset-level lookup tables                                                                                                                                                                                                             |
| `src/oa_structs.rs`              | OpenAlex JSON schema structs                                                                                                                                                                                                            |
| `src/semantic_ids.rs`            | Semantic ID generation for frontend URL slugs                                                                                                                                                                                           |
| `src/agg_tree.rs`                | Hierarchical aggregation tree construction                                                                                                                                                                                              |
| `src/filter.rs`                  | Entity filtering (alias-aware counting + owner-pin filter from the ledger); forced-œuvre + claim passes (pinned owners' works and claimed DOIs ride through type/citation screens); writes `filter_manifest.json` + `forced_works.json` |
| `src/csv_writers.rs`             | CSV output for validation                                                                                                                                                                                                               |
| `src/biblo_var_att.rs`           | Variable-length bibliographic attribute handling                                                                                                                                                                                        |
| `src/peers.rs`                   | KD-tree peer finding: `PartitionedTrees`, `Embed<D>`, `GenericPeerCtx`; log-PCA embedding, distance primitives                                                                                                                          |
| `src/user_ledger.rs`             | Loads + resolves the user ledger snapshot (stable OA id → BigId → dm_id); applies aliases/disowns/claims/owner-pins; merges the step manifests into `applied_manifest.json`                                                             |
| `src/steps/a1_entity_mapping.rs` | Parse CSVs; dedup + map entity IDs; year filtering; ledger drop-side skips                                                                                                                                                              |
| `src/steps/a2_init_atts.rs`      | Init attributes (DOIs, ORCIDs, biblio, topics, locations); Levenshtein name dedup; Nobel category; ledger alias/merge application                                                                                                       |
| `src/steps/derive_links1.rs`     | work→subfields, work→institutions, work→countries                                                                                                                                                                                       |
| `src/steps/derive_links2.rs`     | work→sources; top source per work; per-source `journal_vals` (SCImago-quartile quality only, h-index-free); per-entity top-5 journal relation (quality × paper-count^β); per-subfield citation arrays                                   |
| `src/steps/derive_links3.rs`     | Coauthor networks; hit papers; page filter + semantic IDs; unified peer discovery via `PeerConfig`; topic creator/dominator tags (`topic_tags.rs`, see `topic-tags.md`)                                                                 |
| `src/steps/derive_links4.rs`     | Per-entity hit-paper sorted lists; author citing-hit sets; hit paper semantic IDs + peers                                                                                                                                               |
| `src/steps/derive_links5.rs`     | Era records (yearly citations, top journals/authors/subfields) for hit papers                                                                                                                                                           |
| `src/gen/`                       | Generated Rust source — **do not edit manually**                                                                                                                                                                                        |

### rankless_trees — tree query library

| File                   | Role                                                                                                                                                                                                                                                                                                                                                             |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/interfacing.rs`   | `Getters` struct; loads data interfaces; `make_interfaces!` macro; `RootInterfaces` (sem_ids, peers, hit_sem_ids, hit_dois); `PeerAux`/`build_peer_aux` (per-root peer aux: mmap citing- and ref-subfield profiles + author h-index/year-centroid); `TopRels`/`load_top_rels_map` (per-root top-N relation tables, memory-mapped; hit papers omit country/topic) |
| `src/io.rs`            | `TreeRunManager` (threaded execution: bounded query queue, response-wait timeout, panicking computes answer `Failed`), `CacheKey`, `TreeResponse`, attribute labels                                                                                                                                                                                              |
| `src/path_finder.rs`   | Citation path graph traversal; `RefGraph`; `author_to_work_paths()`                                                                                                                                                                                                                                                                                              |
| `src/work_set.rs`      | `cnf_intersect`: AND-of-ORs intersection over the per-entity `MainWorkMarker` work-lists (sorted ascending by construction — `invert_links_sorted` fills buckets with the monotonic `enumerate` index); smallest-clause base + binary-search membership; `TooBroad` guard                                                                                        |
| `src/ids.rs`           | ID encoding/decoding; `AttributeLabelUnion`                                                                                                                                                                                                                                                                                                                      |
| `src/extensions.rs`    | Extension methods for tree traversal                                                                                                                                                                                                                                                                                                                             |
| `src/instances.rs`     | Concrete tree instances and test configs                                                                                                                                                                                                                                                                                                                         |
| `src/part_iterator.rs` | Incremental tree iteration; `TreeMakingParams`; tree-cache serving (see below)                                                                                                                                                                                                                                                                                   |
| `src/components.rs`    | Tree components (`DisJ`, `IntX`, `PostRefIterWrap`, `CountryInstsPost`); `StackBasis` folding                                                                                                                                                                                                                                                                    |
| `src/prune.rs`         | Tree result pruning                                                                                                                                                                                                                                                                                                                                              |
| `src/arr_ext.rs`       | Array manipulation extensions                                                                                                                                                                                                                                                                                                                                    |
| `src/test_utils.rs`    | Test utilities (`#[cfg(test)]`)                                                                                                                                                                                                                                                                                                                                  |

Key patterns: `BeS<M, E>` (Backend Selector) for flexible data loading; condvar-based
thread pool in `TreeRunManager`.

**Tree cache** — the on-disk `.zst` files under `<data>/cache/<root_type>/<eid>/<tid>/` are the
single source of truth; there is no in-memory done-index and nothing to build at startup. A
request first tries to read+decompress its period file (success ⇒ serve). On miss, cacheable
queries register in `TreeBasisState::in_progress` (`CacheKey → BoolCvp`): the first claimant
computes and writes all period files; concurrent duplicates wait on the cvp, then re-try the
read. The entry is removed and waiters notified on every exit — including panics — via an
RAII guard (`InProgressGuard`); waiters hold their own `Arc` to the cvp, so immediate removal
is safe. Non-cacheable (sub-`CACHEABLE_FROM`) queries skip the registry entirely: no file
will appear, so waiting would only delay the recompute; they still serve a disk file if one
exists (e.g. written before a threshold change). `big_prep`/`big_read` are explicit compute
commands and never serve from cache.

### rankless_server — HTTP API server

Split by concern; `main.rs` holds only the allocator, module declarations, and route wiring.

| File                  | Role                                                                                                                                                                                                                           |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `src/main.rs`         | Allocator (mimalloc), module decls, `main`/`async_main`: `/v1` route table + socket bind                                                                                                                                       |
| `src/consts.rs`       | Server constants (`PORT=3038`, `MAX_HITS=80`, `SEARCH_SIZE=20`, `MAX_SLICE=40k`, `CACHEABLE_FROM=10k`, `N_SUBFIELDS`, `ETYPE_ENC`) + `FIN_*` showcase lists                                                                    |
| `src/responses.rs`    | Wire/DTO + query-param structs (`SearchResult`, `ViewResult`, `PaperOut`, `EntityPeersResp`, `LadderResp`, `Resolve*`, …)                                                                                                      |
| `src/state.rs`        | In-memory state model: `NameState`, `EntityExt` (lean: yearly/start-year/hit-papers; hero relations + co-author network rebuilt per view from mmapped `TopRels`), `IsTop`, type aliases (`StatesT`, `InstTrm`, `NameStateMap`) |
| `src/search_cache.rs` | On-disk cache for the per-entity `SearchEngine` (fnv64 content stamp, load/save)                                                                                                                                               |
| `src/startup.rs`      | Server bootstrap (`get_rest`): parallel per-entity state load (`para_multi_gen_run!`), node stats, `TreeRunManager` build                                                                                                      |
| `src/util.rs`         | Shared handler helpers (`cache_header`, `static_router`, `parse_semantic_id`, `get_empty`)                                                                                                                                     |
| `src/handlers/`       | Axum handlers by concern: `search` (names/slice/sem-id/orcid/resolve), `entity` (views/trees/shallows/ladder/tops + meta), `peers`, `works` (paper sets + DAG + CNF work-set intersection)                                     |

### Supporting crates

| Crate                   | Role                                                                                                                                            |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `dmove` / `dmove_macro` | Metaprogramming: generates entity/attribute/link Rust source tailored to dataset shape (see [Metaprogramming](#metaprogramming--make-pipeline)) |
| `muwo_search`           | Partial-string search engine for entity names: `lib.rs` (trie/engine), `io.rs` (serialization), `fixed_heap.rs`, `merging.rs`, `tests.rs`       |

### Svelte frontend (`src/`)

SvelteKit app; SSR via `+page.server.ts`; all visualizations hand-written SVG (Cytoscape.js
the only viz dependency).

**Types & constants**

| File                          | Role                                                                                                                                        |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `lib/tree-types.ts`           | `TreeGen<T>`, `View`, `Paper`, `RelatedEntity`, `SearchResult`, `TreeResponse`, `BreakdownSpec`, `RootType`, `EntityType`, `InstRel`        |
| `lib/constants.ts`            | `BE_URL`, `ENTITY_TYPES`, `MAX_LEVEL_COUNT=4`, `DEFAULT_LIMIT_N=10`, `COMPLETE_YEAR=1950`, ORCID endpoints                                  |
| `lib/v_constants.ts`          | `VERSION`, `LAST_MOD` build-time info                                                                                                       |
| `lib/types.ts`                | `SurveySubmit`, `SurveyRecord`                                                                                                              |
| `lib/types/showcase.ts`       | `ShowcaseData` and parts — shape of the baked `homepage-showcase.json` consumed by `FeatureShowcase.svelte`                                 |
| `lib/types/release-report.ts` | `ReleaseReport` and parts — shape of the baked `release-report.json` (`pyscripts/release_report.py`) rendered at `/release`                 |
| `lib/types/review.ts`         | Ledger-review types: `WorkRecord`/`OrcidRecord` (enrichment cache), `ReviewVerdict`, `AdminReviewRow`; mirrors `pyscripts/review_ledger.py` |

**Utility modules**

| File                              | Role                                                                                                                                                               |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `lib/tree-functions.ts`           | Tree traversal/flattening/filtering; `getDefaultBreakdowns()`, `getBreakdownOptions()`                                                                             |
| `lib/tree-events.ts`              | Click/hover/selection handlers                                                                                                                                     |
| `lib/visual-util.ts`              | `rescale()`, `getSankeyPath()`, `pinRange()`                                                                                                                       |
| `lib/metric-calculation.ts`       | Specialization scores, impact metrics                                                                                                                              |
| `lib/network-util.ts`             | Co-authorship graph utilities (light layouts)                                                                                                                      |
| `lib/utils/author-timeline.ts`    | Aggregates co-authors from the full loaded works into per-year, span-bounded rows (`buildCoauthors`/`sortCoauthors`/`yearDomain`/`makeTicks`) for `AuthorTimeline` |
| `lib/network-force.ts`            | Cytoscape/fcose force layout — lazily imported so the vendor chunk stays off initial load                                                                          |
| `lib/route-functions.ts`          | URL builders                                                                                                                                                       |
| `lib/loading-functions.ts`        | Data fetching orchestration                                                                                                                                        |
| `lib/text-format-util.ts`         | Number/text formatting; `semantify` + `SEM_MAP` (see [breakdown selection](#breakdown-selection))                                                                  |
| `lib/style-util.ts`               | CSS/SVG styling                                                                                                                                                    |
| `lib/stores.ts`                   | Svelte reactive stores                                                                                                                                             |
| `lib/sitemap-functions.ts`        | SEO sitemap helpers                                                                                                                                                |
| `lib/util.ts`                     | General utilities                                                                                                                                                  |
| `lib/utils/ledger-effective.ts`   | Derives effective disowned/ledger sets for `AllWorks` from applied + pending events                                                                                |
| `lib/utils/works-loader.ts`       | Shared paginated author-works store (`createWorksLoader`); one instance per hero page feeds both `AllWorks` and `AuthorNetwork` so works are fetched once          |
| `lib/utils/works-intersection.ts` | `fetchWorkIntersection`: encodes a CNF `WorkSetQuery` (`$lib/types/work-set.ts`) into the `/works-intersect/*spec` path and returns a `PaginatedPaperSetResp`      |
| `lib/hero-config.ts`              | Per-root-type `HERO_CONFIG` + chip/leader/field-topic builders for `EntityHero` (stat, badge policy, leaders, topics nested under their parent field)              |

**Routes**

| Route                                                                                                    | Role                                                                                                                                                                                                                                                                                                                                 |
| -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `(stat)/`                                                                                                | Home; top entity lists                                                                                                                                                                                                                                                                                                               |
| `(stat)/[rootType]/[...semanticId]/`                                                                     | Entity hero page (tree + network + map; ledger panel for owners)                                                                                                                                                                                                                                                                     |
| `(stat)/[rootType]/table/`                                                                               | Sortable/searchable entity stats table                                                                                                                                                                                                                                                                                               |
| `(stat)/about/`, `(stat)/survey/`, `(stat)/privacy/`                                                     | About / survey / privacy notice                                                                                                                                                                                                                                                                                                      |
| `(stat)/release/`                                                                                        | Data-release report (baked `release-report.json`; see [deploy.md](deploy.md))                                                                                                                                                                                                                                                        |
| `(stat)/login/`, `(stat)/logout/`, `callback/`, `dev-login/`                                             | ORCID OAuth + dev bypass                                                                                                                                                                                                                                                                                                             |
| `api/ledger/`, `api/ledger/[event_id]/`, `api/ledger/[event_id]/revoke/`, `api/ledger-status/`           | Ledger CRUD + status                                                                                                                                                                                                                                                                                                                 |
| `(stat)/admin/`, `(stat)/admin/ledger/`                                                                  | Admin overview (users + consents) / ledger review queue (see [ledger-review.md](ledger-review.md))                                                                                                                                                                                                                                   |
| `api/admin/moderate/`, `api/admin/enrich/`                                                               | Bulk approve/reject; chunked external-metadata fetch + hard-evidence auto-accept                                                                                                                                                                                                                                                     |
| `(stat)/email-preferences/`, `api/email-consent/`                                                        | Opt-in email consent form + API (gated by `EMAIL_FEATURE_ON` in `lib/constants.ts`)                                                                                                                                                                                                                                                  |
| `api/papers/{disown,claim,merge}/`, `api/authors/merge-request/`                                         | Legacy paper/author actions (forward to ledger; slated for removal)                                                                                                                                                                                                                                                                  |
| `tiles/[rootType]/[...semanticId]/`                                                                      | Treemap visualization                                                                                                                                                                                                                                                                                                                |
| `(stat)/game/`                                                                                           | Games hub linking the two games (also keeps pre-split `/game` share links working)                                                                                                                                                                                                                                                   |
| `(stat)/game-clues/`, `api/game-clues/`                                                                  | "Guess the institution" daily/practice game over `game-card` objects from the MCP object store; only the daily card ships with the page — practice cards load on demand (GET), results POST into `game_results`                                                                                                                      |
| `(game)/game-homeground/`, `api/game-countries/`, `game-countries/`                                      | "Home Ground" speed quiz over `country-card` objects (university names that lie about home; 4 flag options, per-question timer, 3 lives — a miss holds the reveal in a bottom sheet, a run-ending miss leads from it to the result screen); full-viewport phone-first layout outside the `(stat)` header/footer chrome; a freshly shuffled deck ships with the page, practice decks GET, runs POST into `country_game_results` (score, deck size, missed sem-ids); `game-countries/` 301-redirects old links |
| `path-to-person/[aidSrc]/[aidTarget]/`                                                                   | Collaboration path finder (built; not linked from live nav — see `unfinished-features.md`)                                                                                                                                                                                                                                           |
| `oa-id/[oaId]/`                                                                                          | OpenAlex ID → entity redirect                                                                                                                                                                                                                                                                                                        |
| `api/survey/`, `pic/.../{breakdown.svg,breakdown.png}/`, `pic/home.png/`, `sitemap*.xml/`, `robots.txt/` | Survey / dynamic SVG + rasterized entity & homepage OG cards / SEO                                                                                                                                                                                                                                                                   |

**Key components**

| Component                                                                                                  | Role                                                                                                                                                                                                                                                                                                                                                                                                      |
| ---------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `TreeSvg.svelte`                                                                                           | Main hierarchical breakdown tree                                                                                                                                                                                                                                                                                                                                                                          |
| `ConceptMap.svelte`                                                                                        | Research-space field network                                                                                                                                                                                                                                                                                                                                                                              |
| `AuthorNetwork.svelte`                                                                                     | Co-author panel hosting a network/timeline tab toggle. Network: co-authorship graph (Cytoscape); click a node/edge to browse papers shared with that co-author (or both) via the shared `works-loader`. On an edge whose hero-three-way set is empty, offers the pair's own two-way intersection via `works-intersection.ts`. Switching to timeline triggers `works.loadAll()`                            |
| `AuthorTimeline.svelte`                                                                                    | Band-style co-author timeline (every collaborator from the full work set, incl. unlinkable discarded authors): per-row span bar + per-year marks, hit highlighting, hover tooltip, min-shared-papers + sort controls; built from `lib/utils/author-timeline.ts`                                                                                                                                           |
| `WorldMapSvg.svelte`                                                                                       | Geographical citation impact map                                                                                                                                                                                                                                                                                                                                                                          |
| `GameShell.svelte`                                                                                         | Centered-card frame for the games hub and the clue game: title + streak header, and their shared chrome classes (`intro`/`mode-row`/`actions`/`reveal`/`verdict`/`error`)                                                                                                                                                                                                                                 |
| `GameFrame.svelte`                                                                                         | Full-viewport (100svh, no scroll) phone-first frame for the arcade games (`/game-homeground`, the ranking game next): hub link + mode label + streak header, plus shared `:global` chrome — the palette-ramp bar (`.ramp-bar`), big buttons (`.g-btn`), status-colored hearts (`.hearts`), and the `--game-sub` sub-label color                                                                             |
| `GameGuessMap.svelte`                                                                                      | Click-to-pin world map for the game: same country-paths asset, inverse projection from `map-projection.json` (fit by `pyscripts/calibrate_map.py`), reveal marker + distance                                                                                                                                                                                                                              |
| `TileTreeMap.svelte`                                                                                       | Treemap view                                                                                                                                                                                                                                                                                                                                                                                              |
| `PaperRainbow.svelte`                                                                                      | Hit-paper citation area chart with scrollable list                                                                                                                                                                                                                                                                                                                                                        |
| `HitPaperBreakdown.svelte`                                                                                 | Lazy citation breakdown for a single hit paper                                                                                                                                                                                                                                                                                                                                                            |
| `ImpactDag.svelte` / `DagChip.svelte`                                                                      | Citation impact DAG + paper chips                                                                                                                                                                                                                                                                                                                                                                         |
| `AllWorks.svelte`                                                                                          | Paginated author paper list (reads the shared `works-loader`); ledger/disown UI                                                                                                                                                                                                                                                                                                                           |
| `AuthorLedgerPanel.svelte`                                                                                 | Owner's profile-changes panel (applied/pending events)                                                                                                                                                                                                                                                                                                                                                    |
| `AuthorOwnerTools.svelte`                                                                                  | Legacy owner action UI (slated for removal)                                                                                                                                                                                                                                                                                                                                                               |
| `ExportControls.svelte`                                                                                    | Sort/filter/citation-style/BibTeX controls                                                                                                                                                                                                                                                                                                                                                                |
| `EntityHero.svelte`                                                                                        | Hero-page header, config-driven per root type (`$lib/hero-config.ts`): per-entity stat, specialization field chips (standing badge except countries) that nest each field's top topics, tailored leader rows, decade chart                                                                                                                                                                                |
| `InfoTip.svelte`                                                                                           | Unified "what is this?" tooltip: small `i` badge (or inline-text) trigger, opens on hover/focus/tap, solid background positioned at the trigger and clamped to the viewport. Used by `IndexedCitationLink`, `HeadControl` (Specialization / since-year), `HeroFieldBlocks` (papers-in note), `AxesOfFocusReach`                                                                                           |
| `IndexedCitationLink.svelte`                                                                               | "indexed" citation explainer (wraps `InfoTip`; shared across stat-line variants)                                                                                                                                                                                                                                                                                                                          |
| `Peers.svelte` / `BarChart.svelte`                                                                         | Peer comparison bars + shared span-bar chart                                                                                                                                                                                                                                                                                                                                                              |
| `DominatedTopics.svelte`                                                                                   | "Topic Leadership" list (entity's dominated topics)                                                                                                                                                                                                                                                                                                                                                       |
| `WorkElem.svelte`, `SearchResults.svelte`                                                                  | Single paper / search autocomplete                                                                                                                                                                                                                                                                                                                                                                        |
| `ScrollyGraph.svelte` / `ScrollySank.svelte` / `TimelineViz.svelte`                                        | Scrollytelling + timeline viz                                                                                                                                                                                                                                                                                                                                                                             |
| `PathLevelInfoBox.svelte` / `MidpathBar.svelte`                                                            | Path UI                                                                                                                                                                                                                                                                                                                                                                                                   |
| `HeadControl.svelte`, `Toc.svelte`, `FlatOutFrame.svelte`                                                  | Header / sticky nav / flat-view frame                                                                                                                                                                                                                                                                                                                                                                     |
| `FeatureShowcase.svelte`                                                                                   | Homepage "Latest features" section: per-feature cards (Login, Hit-papers, Co-author timeline, Peers, Co-authors; All works + export demoted to the text-only "And more" grid). Reads the baked `homepage-showcase.json` (zero backend calls on load); composes the four data previews below                                                                                                               |
| `ShowcaseRainbow.svelte` / `ShowcaseTimeline.svelte` / `ShowcasePeers.svelte` / `ShowcaseCoauthors.svelte` | Static, real-data previews for the showcase: a mini hit-paper rainbow (arcs by citations); a compact co-author timeline (spans + per-year marks, hit-flagged); a hero-vs-peer comparative bar pair (by field + by year); a ring-layout co-author mini network (no Cytoscape)                                                                                                                              |
| `HomeCard.svelte`                                                                                          | Brand homepage OG card (wordmark, tagline, live `/counts` figures with `BRAND_STATS` fallback, spectrum breakdown bar); typeset in the revamp faces — Hedvig Letters Serif/Sans + Space Mono, vendored in `static/fonts/` and installed into the runner's fontconfig by `deploy.py` so `rsvg-convert` uses them. Server-rendered to standalone SVG (no `<style>`/CSS vars), rasterized via `pic/home.png` |

| `LedgerClaimantGroup.svelte` / `LedgerEventRow.svelte` / `LedgerQueueFilters.svelte` / `VerdictBadge.svelte` / `OrcidLink.svelte` | `/admin/ledger` review queue: per-claimant collapsible batches, enriched event rows (DOI/OpenAlex links, auto/proven badges, expandable AI verdicts), URL-driven filters + pager |

**Server utilities**

| File                              | Role                                                                                                                                                                                                                                                                                                                                                |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `lib/server/session.ts`           | ORCID session management                                                                                                                                                                                                                                                                                                                            |
| `lib/server/db.ts`                | SQLite singleton (`bun:sqlite`, WAL); ledger + review tables (`subject_enrichment`, `review_verdicts`)                                                                                                                                                                                                                                              |
| `lib/server/render.ts`            | `renderSvgComponent` — Svelte 5 `svelte/server` `render()` to HTML string                                                                                                                                                                                                                                                                           |
| `lib/server/share-card.ts`        | Shared breakdown-SVG build (used by `breakdown.svg`/`.png`) + SVG→PNG entity & homepage OG cards                                                                                                                                                                                                                                                    |
| `lib/server/card-raster.ts`       | `rsvg-convert` rasterizer + best-effort disk cache for OG share cards                                                                                                                                                                                                                                                                               |
| `lib/server/id_resolver.ts`       | Resolves UI entity refs to stable-ID payload blocks                                                                                                                                                                                                                                                                                                 |
| `lib/server/ledger-hash.ts`       | `subject_hash` computation for ledger dedup                                                                                                                                                                                                                                                                                                         |
| `lib/server/enrich.ts`            | Pure fetch+pluck of Crossref/OpenAlex work + ORCID person records (the app's only external-metadata fetcher)                                                                                                                                                                                                                                        |
| `lib/server/review.ts`            | Pure review-domain logic: DOI/ORCID canonicalization, hard-evidence rule, verdict picking, `AdminReviewRow` composition                                                                                                                                                                                                                             |
| `lib/server/review-data.ts`       | DB glue: `runEnrichment` (chunked cache fill + auto-accept), `loadReviewQueuePage`                                                                                                                                                                                                                                                                  |
| `lib/utils/reference-format.ts`   | Academic reference formatting (APA/MLA/Chicago, BibTeX)                                                                                                                                                                                                                                                                                             |
| `lib/utils/paper-helpers.ts`      | Paper/author/source name resolution; highlight detection                                                                                                                                                                                                                                                                                            |
| `lib/utils/dag-builder.ts`        | DAG construction from RefTree                                                                                                                                                                                                                                                                                                                       |
| `lib/utils/impact-summary.ts`     | Summary counts (Nobel, Science/Nature, standout) for citing papers                                                                                                                                                                                                                                                                                  |
| `lib/utils/clipboard-download.ts` | Clipboard copy + file download                                                                                                                                                                                                                                                                                                                      |
| `lib/utils/game.ts`               | Shared game plumbing: day stamp, streak rule, FNV daily pick, shuffle, flags + `Intl` country names, share-text frame, localStorage state, result-POST + clipboard helpers                                                                                                                                                                          |
| `lib/utils/game-clues.ts`         | Clue-game math: map↔lat/lon projection, haversine, distance×clue scoring, share text (types in `lib/types/game-clues.ts`)                                                                                                                                                                                                                           |
| `lib/utils/game-countries.ts`     | Country-game rules: lives, question timer, random capped deck build (answer folded into shuffled options), share text (types in `lib/types/game-countries.ts`)                                                                                                                                                                                      |
| `lib/server/game-common.ts`       | Shared server plumbing for the games: lazy per-game schema setup (with guarded column adds for already-deployed tables), boundary validators, capped JSON body reader                                                                                                                                                                               |
| `lib/server/game-clues.ts`        | Server side of the clue game: pack reads over the object store (`GAME_PACK_ETYPE` picks the served pack), daily/practice card picks with facts stripped, `game_results` log + boundary validation                                                                                                                                                   |
| `lib/server/game-countries.ts`    | Server side of the country game: `country-card` pack reads + serve-time badge enrichment (top-percentile subfield standings computed from `/peers` + `/ladder` with the hero's own peers-utils machinery, cached per process; a card without a standing never serves), freshly shuffled decks, `country_game_results` run log + boundary validation |
| `lib/server/objects.ts`           | Read/review access to the MCP object store (index rows + cached zstd bundle reads; written by pyscripts, see [mcp-server.md](mcp-server.md)): `/game-clues` and `/game-countries` consume current cards, `/mcp` reviews and presents; SQL shared with the e2e seeder via `objects-schema.ts`                                                        |
| `hooks.server.ts`                 | SvelteKit middleware                                                                                                                                                                                                                                                                                                                                |

### Python scripts (`pyscripts/`)

| File                                                                            | Role                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `__main__.py`                                                                   | Unified CLI (`uv run -m pyscripts <command>`): a `protocli` Dispatcher over lazily-imported command modules — a module exposes a typed `main(...)` (its signature is the parser) or a nested `_dispatcher`; `--help-all` prints every parser                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| `cache_prompting.py`                                                            | Query infrastructure: `BatchRequester`, `get_specs_and_ys`, `get_resdf`, URL gen; `addr` configurable                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| `server_ops.py`                                                                 | `ServerProcess`, `DockerServer`/`FlaskPgServer`, self-healing `build_image()`, `build_server()`, `current_branch()`, `checkout()`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `stow_ops.py`                                                                   | `StowManager` (rsync stash per branch), `RebuildLevel`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `bm.py`                                                                         | Benchmark suite: latency/throughput/memory across branches                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `branch_comparison.py`                                                          | Branch-to-branch structural diff + timing (see [benchmarking](benchmarking.md))                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `sql_comparison.py`                                                             | Flask/PostgreSQL vs Rust diff + benchmark; two Docker containers                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| `comparison_driver.py`                                                          | Shared comparison skeleton: `prepare_backend`, `sample_entities`, `run_query_loop`, `write_artifacts`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| `tree_diff.py`                                                                  | Structural diff primitives: `flatten_tree`, `make_diff_df`, `metric_stats`, `top_source_stats`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `comparison_report.py`                                                          | Shared report generation: `CompResult`, summary/grouped DFs, plots, md/HTML                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| `poster_figures.py`                                                             | Brand-palette SVG/PDF figures from a run's CSVs for the ICWE poster (see `logs/POSTER.md`)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `export_user_ledger.py`                                                         | Exports SQLite ledger → `$OA_ROOT/user-ledger/` snapshot before `filter`; stamps each event's merge-stable logical key (`orcid\|kind\|subject_hash`) and resolves revokes away                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `ledger_ids.py`                                                                 | Python side of the ledger's identifier + subject-key rules (canonical DOI/ORCID, author subject shape, merge subject hash) — one mirror of `src/lib/utils/identifiers.ts`, `src/lib/server/ledger-hash.ts` and `rankless_rs/src/user_ledger.rs` for everything that writes ledger rows from Python                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `claims.py`                                                                     | Paper-claim release lane (`uv run -m pyscripts claims <step>`): `review-merges` (y/n per name-matched candidate, decision written back into the plan), `apply-merges`, `accept` (only what the snapshot proves; stamped `auto:snapshot-authorship`), `record` (the release's `releases/<run_id>.claims.json` sidecar — publishable aggregates at the top level, per-claim detail under `detail`, which never leaves the box). Every case-specific decision lives in the per-release plan file, never in the repo                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| `review_ledger.py`                                                              | AI review lane (`uv run -m pyscripts review-ledger`): per-claimant agentic sessions (explore/runner.py engines + rankless MCP) over the `subject_enrichment` evidence bundles → structured `review_verdicts` for `/admin/ledger`; see [ledger-review.md](ledger-review.md)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `deploy.py`                                                                     | Application/box deploy: EC2 primitives (Nginx, systemd, SSL, code push, user-DB handoff) + ship_alpha/promote with smoke checks (`uv run -m pyscripts deploy <action>`)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `recalc.py`                                                                     | Data recalculation stages: refresh-data, commit-artifacts, warm-caches (`uv run -m pyscripts recalc <stage>`, see [deploy](deploy.md)); ship_alpha/promote live in `deploy.py`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `release_report.py`                                                             | Pure release-record → public report derivation; bakes `src/lib/assets/data/release-report.json` (rendered at `/release`), `--md` promo digest, and the promote gate's report↔served-version assert                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `cohort_baseline.py`                                                            | Snapshots each pinned owner's served works/citations to `$OA_ROOT/releases/<run_id>.cohort.json` while a release is live — the release-over-release attribution baseline                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `gitutil.py`                                                                    | Shared local-git plumbing (`git`/`git_out`/`git_lines`, `current_branch`, `head_commit` + the `HEAD_CMD` 12-char form matching `build.rs`, `assert_pushed`) used by recalc/deploy/fleet                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `fleet/` (`config`, `remote`, `manifest`, `preflight`, `drive`, `calibrate`)    | Cache-warm worker fleet over the machine-local `data/warm.toml`: validated band config, ssh/rsync transport, data manifest + stamp, preflight invariant gate, phased driver (prepare → gate → compute → coverage gate), probe/suggest calibration helper, standalone `prepare` (converge + gate, no compute) (`make fleet-<action>`)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| `live_monitoring.py`                                                            | Health monitoring + email alerts                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| `log_parsing.py`, `report.py`                                                   | Nginx log parsing + hourly performance reports                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| `make_test_dataset.py`, `lib_data_generation.py`                                | nano/micro/mini subset generation                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `homepage_showcase.py`                                                          | Bakes `src/lib/assets/data/homepage-showcase.json` (one featured scholar's hit papers, co-author timeline, hero-vs-peer comparison, and co-author network) for the homepage showcase; run via `make homepage_showcase` against a live backend (`SHOWCASE_BE=…/v1` overrides the default `127.0.0.1:3038`)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `extend_csvs.py`                                                                | CSV transforms: source area-fields, quartiles, author wiki-slugs, Nobel categories                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| `sitemap_validation.py`, `survey_result_export.py`, `nobel.py`, `svg_export.py` | Sitemap / survey / Nobel / SVG export utilities                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `calibrate_map.py`                                                              | Fits the world-map asset's (linear) projection against per-country institution-coordinate medians; bakes `src/lib/assets/data/map-projection.json` for the game's click→lat/lon inversion                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `object_store.py`                                                               | Unified MCP object store: immutable per-run bundles (`data/mcp-objects/<run>.jsonl.zst`) + payload-free version index (`mcp_objects` in `data/rankless.sqlite`, keyed `(kind, obj_key, bundle)`, latest non-rejected wins); CLI `uv run -m pyscripts objects {list,ingest,export,set-status,fsck}` (`fsck` verifies every row's bundle address; exports compress to `.zst`); `gen_at` is stamped UTC ISO at write time; bundles ride the artifact-dir copy, index rows the user-DB handoff (see [mcp-server.md](mcp-server.md))                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| `explore/`                                                                      | Agent reasoning over the data: `paths/{bugs,features,stories}.py` review Playwright snapshots (`make explore`); `deep.py` (`uv run -m pyscripts.explore.deep`, `make deep-explore`) drives an agentic session with the `mcp_server/` tools against a chosen backend (foci: share/query/data-issue + endpoint suggestions; `--subject`/`--question`/`--investigate` scoping), re-issuing every cited number and writing story-only `report.md` + `reproduce.md` + `findings.json` (+ `runs.jsonl`) to `.cril/writeups/explorations/`; `runner.py` pluggable mining engines (`--runner`, claude-cli today), `cli.py` headless-Claude runner (optional MCP), `evidence.py` snapshot loading, `verify.py` deterministic re-issue of model-cited tool calls (`verify_facts`, shared by every workflow), `runs.py` shared agent-run identity (`<workflow>-<scope>-<UTC stamp>` names, session open/close, the worker's `WORKFLOWS` registry), `generation.py` the shared engine for object-store generator workflows (target picking, concurrent mining, bundling, session + report), `game_cards.py` (`uv run -m pyscripts game-cards`) verified + leak-linted 6-clue ladders as `game-card` objects, `country_cards.py` (`uv run -m pyscripts country-cards`) batch-prompted (no per-entity agentic session) misleadingly-named-institution quiz cards with ISO-validated decoy countries as `country-card` objects, `impact_stories.py` (`uv run -m pyscripts impact-stories`) verified per-entity impact narratives as `impact-story` objects |
| `build_mcp_manifest.py`                                                         | Bakes `src/lib/assets/data/mcp-manifest.json` for the `/mcp` page from the live tool docstrings / foci / argparse help / resources / prompts (`make mcp-manifest`); see [mcp-server.md](mcp-server.md)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `mcp_worker.py`                                                                 | Host worker (`make mcp-worker`, systemd) that runs admin-queued sessions via the `explore/runs.py` `WORKFLOWS` registry (`params.type`; deep when absent) and ingests them into the `mcp_sessions` store (on startup re-queues orphaned `running` rows it owns — never self-registered CLI runs, marked `params.origin`). Frontend store: `src/lib/server/mcp-sessions.ts`; routes `/mcp` (docs + sessions, admin controls inline), `/mcp/runs/[name]`. See [mcp-server.md](mcp-server.md)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `userdb.py`                                                                     | The user-data unit (`data/rankless.sqlite` + `data/mcp-sessions/` + `data/mcp-objects/`): consistent snapshots, cross-box table transfer with decision reconciliation, and retained off-box backups (`uv run -m pyscripts userdb {transfer,snapshot,backup}`); deploy.py provides the transport (see [deploy.md](deploy.md) → Backups, [mcp-server.md](mcp-server.md) → Moving sessions between boxes)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| `services.py`                                                                   | Unified service setup (`make setup-services ARGS="--profile dev"`): renders the `deploy/` systemd unit templates (`{{ var }}` placeholders) with real machine values (repo root, data root, MCP backend URL toggle) and installs them into `~/.config/systemd/user`; profiles dev / small-alpha / live / worker pick which of backend, frontend blue+green, mcp-server, mcp-worker run. `deploy.py` renders the same templates over SSH                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `migration_scripts/`                                                            | One-time catch-up scripts for already-deployed state (`python3 -m pyscripts.migration_scripts.<name>`, stdlib-only so they run on a serving box's runtime venv). The app, the pipeline and the ops commands only ever speak the current schema and formats — never a version check, never a branch for an older shape; when a change strands a deployed database or data directory, the catch-up lands here, runs once per box and is deleted with the same commit that stops needing it                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |

### Type audit (`pyscripts/typeaudit/`)

Cross-language type/API-shape coherence audit (`uv run -m pyscripts.typeaudit`,
`make type-audit`); see [type-audit.md](type-audit.md).

| File           | Role                                                                                         |
| -------------- | -------------------------------------------------------------------------------------------- |
| `__main__.py`  | Orchestration: response/ledger/gen families, the Rust↔TS pairing, directional diff, report   |
| `rustparse.py` | Serde-aware Rust struct/enum parser (`rename`/`rename_all`/`flatten`/`skip`) → JSON key sets |
| `tsparse.py`   | TS `type`/`interface` + `kind`-union parser → key sets                                       |

### MCP server (`mcp_server/`)

Python MCP proxy (stdio, `uv run -m mcp_server` / `make mcp-server`) exposing the Rust
backend to any MCP client; see [mcp-server.md](mcp-server.md).

| File                  | Role                                                                                                     |
| --------------------- | -------------------------------------------------------------------------------------------------------- |
| `server.py`           | FastMCP wiring: registers tools/resources/prompts, stdio transport                                       |
| `tools.py`            | Tool implementations as plain async functions (`TOOL_FNS` registry, reused by the deep-stories verifier) |
| `client.py`           | Async httpx client for the backend (`RANKLESS_BE_URL`, default `127.0.0.1:3038/v1`)                      |
| `response_shaping.py` | Tree flattening via `/v1/specs` breakdowns, list truncation, `rankless_url` backlinks                    |
| `resources.py`        | Static schema/guide resources (`rankless://schema/entity-types`, `rankless://guide/agent`)               |
| `prompts.py`          | Reusable prompts (`author_impact_report`)                                                                |

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
`subfields`, `hit-papers`. Each entity has _production_ (own papers) and _impact_ (papers
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
mod` up to `<step>`), and `gen/mod.rs` (all _previously completed_ gen files, not the
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

| Module                                   | Mechanism                                   | Parallelized work                       |
| ---------------------------------------- | ------------------------------------------- | --------------------------------------- |
| `rankless_rs/steps/a2_init_atts.rs`      | `Worker<T>::para()`                         | CSV rows: works, biblios, authorship    |
| `rankless_rs/steps/a1_entity_mapping.rs` | `std::thread::spawn` + `Vec<JoinHandle>`    | Independent entity ID mapping           |
| `rankless_rs/steps/derive_links2.rs`     | `par_join!`                                 | 5 `CiteDeriver` methods                 |
| `rankless_rs/steps/derive_links3.rs`     | `para_multi_gen_run!` + `Worker<T>::para()` | Work counts per entity; peer selection  |
| `rankless_rs/src/common.rs`              | `make_interface_struct!`                    | Parallel data loading at server startup |
| `rankless_trees/src/io.rs`               | Persistent pool (`VecDeque` + `Condvar`)    | Tree query serving; 16 threads          |
| `rankless_server/src/main.rs`            | `para_multi_gen_run!` + Tokio (16 workers)  | Entity state init; HTTP handling        |

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

**Testing & coverage:**

| Command                 | What runs                                                                                                                                                                               |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `bun run test`          | Playwright e2e (`tests/`, builds + previews on 4173). `ledger.spec.ts` is excluded via `testIgnore`                                                                                     |
| `make mega_test`        | The ledger integration test (`ledger.spec.ts`) — orchestrates dev server + backend + a pipeline run between its `pre-pipeline`/`post-pipeline` phases via `playwright.ledger.config.ts` |
| `bun run test:unit`     | Vitest unit tests (`src/**/*.test.ts`) — the TS logic in `src/lib`                                                                                                                      |
| `bun run test:unit:cov` | Vitest with V8 coverage of `src/lib/**/*.ts` → `coverage/index.html`                                                                                                                    |
| `bun run test:e2e:cov`  | Playwright (same specs as `bun run test`) with browser coverage → `coverage-e2e/index.html`                                                                                             |
| `make coverage`         | Runs `test:unit:cov` + `test:e2e:cov` (failures tolerated — the reports still generate), then opens both reports in Firefox                                                             |

`test:e2e:cov` builds with `COVERAGE=1` (inline sourcemaps via `vite.config.ts`) and collects
Chromium V8 coverage per test (`tests/coverage/fixtures.ts`), which `monocart-coverage-reports`
remaps through the sourcemaps back to `.svelte`/`.ts` (`global-setup`/`global-teardown` clean +
merge). Specs import `test`/`expect` from `tests/coverage/fixtures` so the collector is a no-op
when `COVERAGE` is unset.

Only **browser-side** execution is captured: the app's SSR imports `bun:sqlite`, so build +
preview must run under bun, which has no `NODE_V8_COVERAGE` equivalent for a long-running server
— the node path that would dump SSR coverage can't load `bun:` URLs. Component logic is still
covered (it runs during hydration); the gap is SSR-only `.ts` (load functions, `+server.ts`,
hooks), part of which the vitest unit suite already exercises.

**Where things live:** `data/nano-snapshot/` (downloaded JSON, gitignored),
`data/nano-root/` (local pipeline output, gitignored), `libs/ccl-science-data` (symlink →
`~/.cache/rankless/ccl-science-data`; override with `CCL_CLONE_DIR=<path>`),
`target/release/rankless-server`, `.env` (gitignored, seeded from `.env.example`).

**Troubleshooting:**

| Symptom                         | Fix                                                                             |
| ------------------------------- | ------------------------------------------------------------------------------- |
| `port 3038/5173 already in use` | `lsof -nP -iTCP:3038 -sTCP:LISTEN` to find the other instance                   |
| `backend never became ready`    | inspect `make dev` output; usually incomplete OA_ROOT — re-run `make bootstrap` |
| `NANO_ARTIFACT_URL` 404         | the artifact host isn't reachable; get a fresh URL                              |
| ccl-science-data import error   | `rm -rf libs/ccl-science-data && make bootstrap`                                |

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
