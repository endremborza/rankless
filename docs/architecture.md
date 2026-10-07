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
Disciplines**. Discipline hierarchy: Domains → Fields → Subfields →
Topics, ASJC-based.

Core relationships: citations, authorships, topical classifications. Affiliations link
institutions to authorships (author↔paper pairs). Each searchable entity has a hero page
built around **production** (its papers) and **impact** (papers citing those).

The full production dataset's size is served at `/v1/counts` (`total_works`); subset sizes (nano/micro/mini) are used for local dev, CI, and correctness/scale validation.

What counts as a paper: an OpenAlex work of a type in `WORK_SCREEN.kinds`, not retracted, published within the covered years, and not an abstracting service's copy of another paper (a DOI under `work_identity::ABSTRACT_COPY_PREFIXES`, which `WORK_SCREEN.abstract_doi_prefixes` carries: ChemInform records, typed `article`, filed under the abstracted paper's authors). One paper published twice is one paper: a copy-edition record merges into the original edition's record of the same number when the two share an author (`work_identity::EDITION_PAIRS`: Angewandte Chemie's German and International editions; written by `derive-ledger`), so it counts once and its citations add up. Conference papers arrive under three OpenAlex labels — society proceedings (IEEE, ACM) have always been `article`, while proceedings series (LNCS and kin) are typed `book-chapter` in older snapshots and `conference-paper` once OpenAlex retypes them — so the screen keeps all three regardless of snapshot vintage. Works of any type also enter when forced: a pinned owner's œuvre and claim-resolved works ride through the type and citation screens, never through the year, retraction and abstract-copy screen (`admits_publication`). A paper needs one authorship row that names an author record, and there is no ceiling on its authors. What its size changes is who it is credited to (`WORK_SCREEN.team_limit` authorship rows, unresolved ones counted): up to the limit its authors are a team, each other's co-authors, every institution among them credited; above it the paper is on each resolved author's record in full, an institution (and through it a country) is credited only when it is on at least 1 in `team_limit` of the rows (`credits_institution`, applied where `derive_links1` builds `work-institutions`, so every count, ladder and tree downstream reads the thresholded set), and it makes no co-author relation: none in `coauthors` (`derive_links3`), in an entity's top authors (`derive_links2`), or in the co-author tree levels (`Getters::team_ships`). The screen is stated once as `WORK_SCREEN` in `rankless_rs/src/metrics.rs`, and its per-entity minimums as the env's thresholds in `env_consts`, which differ per build environment — `filter.rs` reads them, and the site and the MCP (`get_methodology`) render them from their generated wire constants (`METHODOLOGY`, `env_consts`).

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

**Backend (`rankless_server`):** Axum HTTP server (on `PORT`, `rankless_server/src/consts.rs`) over pre-processed binary
data. Custom partial-string search (`muwo_search`). Proactive cache pre-warming
(`pyscripts/cache_prompting.py`) for high-traffic entities. Peers endpoint pre-loads peer
ID arrays and memory-maps per-subfield citation counts at startup. The per-entity hero
relations (top authors/fields/journals/topics/countries) are memory-mapped top-N tables
rebuilt into the response on demand per entity view, rather than held resident.

**Tree library (`rankless_trees`):** hierarchical query engine with thread pool
(`TreeRunManager`), citation path finder (`path_finder.rs`), in-memory caching.

**Frontend (`src/`):** SvelteKit/Svelte with SSR. All visualizations hand-written SVG;
Cytoscape.js the only external viz dependency. ORCID authentication on author profile
pages. SQLite (`bun:sqlite`, WAL mode) backs an append-only **user ledger** of
profile modifications (disown/claim/merge), plus its review layer: a
`subject_enrichment` cache of external metadata (Crossref/OpenAlex/ORCID) and
AI `review_verdicts`, both surfaced on the `/admin/ledger` moderation queue
(see [ledger-review.md](ledger-review.md)).
A profile page can also carry a **disclaimer** (`profile_disclaimers`, written by `pyscripts disclaimers`): a bordered data note at the bottom of its first card, shown while the data run it was written against is served.

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

| File | Role |
| --- | --- |
| `src/lib.rs` | Module root; exports public API; dispatches pipeline steps (`runner` from the CLI, `run_step` on a prepared `Stowage`) |
| `src/main.rs` | CLI entry; reads `OA_ROOT` env; calls `lib::runner()` |
| `src/common.rs` | `Stowage` (file/data manager; the generated-code dir it writes `gen/<step>.rs` to is redirectable), marker traits, `reverse_id`, type aliases, `MmapBox`, parsing utils |
| `src/csv_iter.rs` | CSV partition readers (`ObjIter<T>` sequential, `par_reduce` one thread per partition) and the ledger lens: with a `ResolvedLedger` on the `Stowage`, rows of `works/main`, `authors/main`, `authorships`, `referenced_works`, `locations`, `topics` and the author enrichment tables `extend_csvs` writes (their bare `oa_id`) read with merged ids as their keep id, drop-side main rows and disowned authorships absent, a reassigned authorship naming its new author (or none: the row stays, unresolved, with its affiliation and position), the forced claims' granted authorships as rows closing the table's first partition, a stripped author's `orcid` cell empty, a keep author's counts summed over its merged records, a renamed author's `display_name`; column roles from the header, once per partition, inert on an empty ledger |
| `src/derived_ledger.rs` | `derive-ledger`: the derived ledger source, run by `make filter` before the filter step. Clusters the author records sharing an ORCID by name (`Name`, `affinity`, `same_person`: shared token information in bits against flat costs for what only one side has; names folded through `deunicode`, so other scripts transliterate; a nickname table and one-edit matches of rare tokens count as the same token at a discount; a two- or three-letter capital block reads both as initials and as a name), lets the cluster the ORCID's registered name matches own it (`NAMES_TABLE` under the external data root — the env var `EXTERNAL_DATA_ROOT`, `DEFAULT_EXTERNAL_DATA_ROOT` when unset; all three `#[wire]`, so `pyscripts/external_data.py` and `orcid_summaries.py` read them — written by `pyscripts/orcid_summaries.py`; without it, the most works), merges the owner's clusters and, under a registered owner with a full given name, the clusters that name does not contradict into the oldest id, and strips the ORCID from the rest; a record over `WORK_SCREEN.max_author_papers` never owns or keeps. A merged person reads with the registered name, else the largest record's, when it has more full name tokens than the keep's own. It also writes the paper merges `work_identity::edition_merges` finds. Writes, beside the exported ledger, `DERIVED_JSONL` (`merge_authors`, `strip_orcid`, `name_author` and `merge_papers` lines in the `ACTIVE_JSONL` shape with `source: "derived"` and a `reason`; paper merges carry no ORCID) and `DERIVED_MANIFEST` (rows read, owners, records, names and paper merges by reason); the module doc states the rule |
| `src/env_consts.rs` | Config constants: the year range (the same in every env) and the env's pipeline thresholds (`MIN_PAPERS_FOR_INST`, `MIN_PAPERS_FOR_SOURCE`, `MIN_AUTHOR_WORK_COUNT`, `MIN_AUTHOR_CITE_COUNT`, `#[wire]`). Generated by `build.rs` from `RANKLESS_ENV`, falling back to the repo-root `.env` when the var is unset, so make and bare cargo/rust-analyzer agree; never hand-edited. Committed with the `full` env's values and skip-worktree'd locally, like its generated wire files (see [type-generation.md](type-generation.md)) |
| `src/data_consts.rs` | Dataset-level lookup tables |
| `static/country-population.csv` | Inhabitants per ISO-2 country code with the year and source of each row (the World Bank's `SP.POP.TOTL`, other named sources for the codes it lacks, e.g. Taiwan), compiled into `a2_init_atts` with `include_str!`; a coded country without a row fails the build, since every coded country gets a page. The root `Makefile` lists it as a prerequisite of `gen/a2_init_atts.rs` |
| `src/oa_structs.rs` | OpenAlex JSON schema structs |
| `src/semantic_ids.rs` | Semantic ID generation for frontend URL slugs |
| `src/agg_tree.rs` | Hierarchical aggregation tree construction |
| `src/filter.rs` | Entity filtering, applying `metrics::WORK_SCREEN`; the ledger's one decision site (`settle_ledger`): `UserLedger::resolve` against two raw id passes (`SnapshotIds::scan`), then one pass over the authorship rows as the merges alone leave them (`ledger_rows`, the lens installed with `ResolvedLedger::merges_only`) settles the events that read or add rows: a disown or a reassignment applies where its row is, a claim where the whole ledger credits the claimant on a record of the claimed work, and a forced claim (the curated ledger's) whose claimant is on no record of the work is granted a row on its most cited one (`Outcomes::grants`). The pinned owners' œuvre and each forced claim's credited record ride through the type and citation screens and pinned authors through step 20, which drops records over `max_author_papers` unless they are merge keeps whose records are each under it (`Outcomes::bound_exempt`); step 14 keeps every work with an authorship row naming an author. Writes `resolved_ledger.json`, `applied_manifest.json` (after step 14, so a claim on a work the screens drop reads `work_screened`) and `forced_works.json`. `check_ledger` (`rankless-rs check-ledger <root>`) prints what the step would apply and skip, by kind and reason, and writes nothing |
| `src/csv_writers.rs` | `to-csv`: flattens the gz JSON-line parts in the snapshot's `data/jsonl/<entity>/updated_date=*` partitions into per-entity zstd CSV parts under `entity-csvs/` (files beside the partitions, `manifest.json` and `works/deleted_ids.csv.gz`, are skipped); an entity with no `.gz` input is an error |
| `src/biblo_var_att.rs` | Variable-length bibliographic attribute handling |
| `src/peers.rs` | KD-tree peer finding: `PartitionedTrees`, `Embed<D>`, `GenericPeerCtx`; log-PCA embedding, distance primitives |
| `src/ladder.rs` | The citation-rank ladder: `LADDER_PCT_BANDS`, the top shares of a field's cohort an entity's citation standing is placed in, loosest first (`#[wire]`, and in `METHODOLOGY` as `ladderPctBands`), and `compute_cit_rank_ladder`, the citation count at each band per subfield over the entities active in it |
| `src/metrics.rs` | The constants every public number is defined by, and the functions over them. The paper score: `PAPER_SCORE` (the bar's top share and blend weights, the sparse-group fallback, the hit multiple, the stored bar's scale), `is_scored` (inside the work screen and up to `LAST_SCORED_YEAR`, the year before the unfinished final one), `encode_bar`/`decode_bar` (a `u16` in units of `1 / PAPER_SCORE.bar_scale` citations; the pipeline scores from the decoded bar, so the stored bar is the definition, and a bar the encoding cannot hold fails the build), `paper_score` = `√(citations / bar)`, `is_hit`. Over a set of papers: `team_share` = `1 / (1 + ln n)`, `top_n_mean` (missing papers count as zero), `h_index`, and `summarize`, one pass and one sort giving the scored count, weighted total, Top-N mean and h-indices (all and since each `H_SINCE` year), which `derive_links4` runs per entity; `TOP_N` is keyed by entity name because this module compiles before the entity types are generated. Also `field_score` over `dampened_size` = `(papers + cohort mean)^FIELD_SCORE_BETA`, the work screen (`WORK_SCREEN`, whose year window comes from `env_consts`, plus `abstract_doi_prefixes` (`work_identity::ABSTRACT_COPY_PREFIXES`) with `admits_publication`, the abstracting-service copies the screen refuses even a forced work, `team_limit` with `is_team` and `credits_institution`, the size up to which a paper's authors are co-authors and above which an institution needs its share of the rows, and `max_author_papers`, the work count above which an author record is an aggregate — read by step 20 and by `derive-ledger`), the constants a pipeline step and the site or the MCP both state (`MIN_TOPIC_SCORE`, the score above which a work carries an OpenAlex topic, read by `a2_init_atts`; `TOP_HIT_PAPERS`, the hit papers an author's impact keeps, `derive_links4`; `MAX_SHARED_PAPERS`, where a co-author pair's shared-paper count stops, `derive_links3`; `SPEC_CORR_RATE`, the uniform share blended into a tree level's specialization baseline, `rankless_trees/src/interfacing.rs`), `METHODOLOGY` (both, plus `TOP_N`, `H_SINCE`, the ladder's `LADDER_PCT_BANDS`, `MIN_TOPIC_SCORE`, `TOP_HIT_PAPERS` and `SPEC_CORR_RATE`, which the server's wired `METHODOLOGY` carries to the site and the MCP server), and the methodology texts (`PAPER_SCORE_TEXTS`, `HIT_PAPER_TEXTS`: templates `fill` completes from `text_vars`, so no text restates a number); the pipeline steps and `filter.rs` read these fields, they do not restate them, and `PAPER_SCORE`, `TOP_N` and the four step constants are `#[wire]`, so TypeScript and Python read them too. Also `Level` (one breakdown level of a tree: entity + citation side, the identity of a first-level profile). The metric registry lives beside the columns it reads, in `rankless_trees/src/metrics.rs` |
| `src/user_ledger.rs` | Ledger types + resolution: `UserLedger` (the derived records, then the curated events, then the site's, plus pins) → `resolve` against `SnapshotIds` (referenced authors with their counts, the carriers of every referenced ORCID, the author row count, every work record of a claimed DOI with its citations) → `ResolvedLedger` (aliases in keep-id space, removed and reassigned edges, the forced claims' granted authorships, stripped ORCIDs, summed keep counts, display names; `row_author` is what an authorship row reads as, for the reader lens and `credit` alike; saved and loaded with a run_id check, applied by the reader lens) and `Outcomes` (pins, pending claims, the merge keeps exempt from the work bound, the disowns and reassignments awaiting their row, decided keys → `grants`, `forced_claim_works`, `manifest`). Event kinds beyond the site's: `reassign_paper` (a work's authorship row on one record reads as another's, or as nobody's; records named by OpenAlex id, so no ORCID is needed; curated only) and `name_author` (a record's display name; derived and curated). `settle` decides the fate of each author and work record in source order: the last entry whose keep the snapshot holds decides, so a curated event replaces a derived record's and a site event both, the replaced event reads `superseded` (as does an earlier reassignment of the same row or name of the same record), and a merge whose keep already merges into its drop reads `merge_cycle`, so the aliases hold no cycle. A record whose derived fate an event replaced holds no claim on its ORCID, and a stripped keep does not own one through the records merged into it. A claim names its paper by DOI (every record carrying it, the most cited first; credit on any applies it), or by the record the claimant saw when it has no DOI or the snapshot has the DOI on no record. A site claim is a status line; a curated claim is forced: a claimant on no record of the paper is granted a row on the most cited one, after its listed rows and without an affiliation, and the record they are credited on rides through the type and citation screens. Every keyed event ends applied or skipped with a reason; a derived file from another author row count, a derived merge into an absent keep, or an ORCID still on two authors after resolution, is a hard error |
| `src/work_identity.rs` | What publishers' DOIs say about work records, the only place a journal or service is named: `ABSTRACT_COPY_PREFIXES` (ChemInform's records, refused by the work screen through `WORK_SCREEN.abstract_doi_prefixes`) and `EDITION_PAIRS` (journals published in two editions, a paper under one number after both prefixes: Angewandte Chemie's German and International editions). `edition_merges`, a pass over the work records and one over their authorship rows, merges each copy-edition record into the lowest-id original-edition record of its number that shares an author with it, since a number alone is not a paper (until 2003 each Angewandte edition numbered its own articles, and covers are still numbered apart); a copy without such a twin stays. `derive-ledger` writes the merges as derived `merge_papers` lines, reason `edition_twin` |
| `src/steps/a1_entity_mapping.rs` | Parse CSVs; dedup + map entity IDs; year filtering |
| `src/steps/a2_init_atts.rs` | Init attributes (DOIs, ORCIDs, biblio, topics, locations, country populations); an author's repeated rows on a work (an OpenAlex duplicate, or a merged record's beside its keep's) join their institutions; Levenshtein name dedup; Nobel category |
| `src/steps/derive_links1.rs` | work→subfields, work→filtered authors, work→institutions: an institution is on a work when `WORK_SCREEN.credits_institution` holds for the authorship rows naming it (every institution of a team's paper; its share of the rows on a larger one) |
| `src/steps/derive_links2.rs` | work→sources; top source per work; per-source `journal_vals` (SCImago-quartile quality only, h-index-free); per-entity top-5 journal relation (quality × paper-count^β), a source-year without a SCImago quartile ranking at `UNRANKED_Q`; the per-entity top-N relations, among them the top `N_TOP_AUTHORS` authors (`TopAuthorsRec`) and `N_AFF_COUNTRIES` affiliation countries (`TopAffCountriesRec`; the same constant bounds a country value in the metric registry); per-subfield citation arrays |
| `src/steps/derive_links3.rs` | Coauthor networks (`coauthors`, from the works whose authors are a team, a pair's count stopping at `MAX_SHARED_PAPERS`); every scored work's bar (`work-bars`, the blend `bars.rs` computes from the year, subfield and subfield-year top-share bars) and the hit papers (the works whose paper score clears `is_hit`); page filter + semantic IDs; unified peer discovery via `PeerConfig`; topic creator/dominator tags (`topic_tags.rs`, see `topic-tags.md`) |
| `src/steps/derive_links4.rs` | Per-entity hit-paper sorted lists; every peer root's score columns from one `metrics::summarize` per entity (`score_roots`: scored-paper count and h-index for all five, h-index since each `H_SINCE` year for all but authors, weighted total paper score for authors, institutions and countries with the team share over each work's authorships, institutions or countries, Top-N mean where the type has an N); author citing-hit sets (the best `TOP_HIT_PAPERS`, Nobel-weighted); hit paper semantic IDs + peers |
| `src/steps/derive_links5.rs` | Era records (yearly citations, top journals/authors/subfields) for hit papers |
| `src/gen/` | Generated Rust source — **do not edit manually** |
| `src/bin/fixture_build.rs` | `fixture-build <dir>`: the synthetic minimal OA snapshot (`<dir>/snapshot`), the ORCID registered-name table (`<dir>/external`, an `EXTERNAL_DATA_ROOT` for `derive-ledger`) + `scenario.json` naming every id the ledger flow can act on; the generator is the tests' own, `#[path]`-included |
| `tests/common/synthetic_oa.rs` | `Scenario`: the synthetic snapshot (pinned owner, keep/drop author pair, an ORCID shared by four records — the over-bound aggregate with the oldest id, the holder's main record, a same-name split-off below the thresholds and a different person with more works, so only the registered name picks the main record — one work per ledger case, bulk sized from `env_consts`), written as gz JSON lines in the `make_test_dataset.py` layout, one part per entity for ordered ingest, plus `write_names_table` for the registered-name table |
| `tests/ledger_pipeline.rs` | Ledger pipeline gate: per test `to-csv → derive-ledger → filter → a1_entity_mapping` in-process; asserts the resolved tables (aliases, strips, summed counts), filter and dm-space membership under the lens (drop rows gone, disowned edges gone, keep credited, the split-off credited to the keep, the aggregate record screened out), the exact applied and derived manifests, the forced-set sidecar, the derived-only counterfactual (a hyperauthored work stays), a reassignment with and without a target, a disown and a reassignment without their row, a site claim on a screened work, forced claims granted their rows and carried through the screens, the most-works fallback without the names table, revoke/reapply, byte-equal determinism, and that a merge into an absent keep leaves the drop side's dm id intact |

### rankless_trees — tree query library

| File | Role |
| --- | --- |
| `src/interfacing.rs` | `Getters` struct; loads data interfaces; `make_interfaces!` macro; `RootInterfaces` (the search side: names, name extensions, semantic ids, OpenAlex ids, plus the citation counts in their per-entity width, which `make_stats_entry_arc` needs in the same shape node entities give it); `RootColumns`/`load_root_columns`/`Getters::columns_for` — the columns: every `dm_id`-indexed attribute a root type keeps loaded, by etype string, the six roots loaded in parallel. Resident for every root: papers, citations, the yearly era records, hit works, peers, the citation-rank ladder, and the hit-paper count + cohort mean derived at load; then a ladder of mmap top-N relation tables from hit papers up to authors (the `SubfieldProfiles` pair, author career centroid served as a calendar year), every peer root adding its scored-paper count and h-index; the score columns beyond those follow the metric portfolio and load per type by name (weighted total paper score, Top-N mean, the recent h-indices, countries' population), and the hit papers' paper scores are computed from the resident per-work bars (`Getters::wbar`); `located` marks the root whose country and city are `Getters` fixed attributes (institutions) |
| `src/metrics.rs` | The metric registry beside the columns: `METRICS`, one `MetricDecl` per metric (id, label, header template, meaning, `ValueType` — count/score/share/year or an entity reference, single or set-valued — `Param`, the `Column`s it reads, `Cost` read or walk, a walk's `Level`); a metric's `Coverage` (the papers it reads, by year: indexed, scored, since a recent h-index year, or the era of yearly counts) is the first of its columns' (`Column::covers`), every indexed paper for a walk, and `texts` appends it to the meaning. Nothing per root is typed but `default_sort`, which `column_registry` asserts the root loads at startup: `MetricDecl::kind(cols, has_profile)` derives global (its columns loaded and their scan under `SCAN_BUDGET_BYTES`) or intricate from `RootColumns::column_bytes`, and settles a walk metric by whether the root's trees yield its `Level`, and `MetricDecl::read` is the one reader of every metric (`Arg` → `Value`); `ERA` (the first and last year with yearly counts) and `RootColumns::era_slices` (the one reader of a year window inside it, summed by `window_sums` and copied by the stats view) |
| `src/io.rs` | `TreeRunManager` (threaded execution: bounded query queue, response-wait timeout, panicking computes answer `Failed`; `first_levels` fans one profile query per entity across the pool), `FullTreeQuery` (`CacheKey` + `Level` + `Command`: `Serve::{Pruned, Wide, Profile}` or the warmer's `BigPrep`/`BigRead`), `TreeSpecs` (`first_level`/`has_level`/`profile_tid`), `FirstLevel` (a profile with `share`: zero only asserted for a complete level), `TreeResponse`, attribute labels |
| `src/path_finder.rs` | Citation path graph traversal; `RefGraph`; `author_to_work_paths()` |
| `src/work_set.rs` | `cnf_intersect`: AND-of-ORs intersection over the per-entity `MainWorkMarker` work-lists (sorted ascending by construction — `invert_links_sorted` fills buckets with the monotonic `enumerate` index); smallest-clause base + binary-search membership; `TooBroad` guard |
| `src/ids.rs` | ID encoding/decoding; `AttributeLabelUnion` |
| `src/extensions.rs` | Extension methods for tree traversal |
| `src/instances.rs` | Concrete tree instances and test configs |
| `src/part_iterator.rs` | Incremental tree iteration; `TreeMakingParams`; tree-cache serving and writing (see below); a big tree's parts spill under the directory the env var `PARTS_ROOT_VAR` names, `DEFAULT_PARTS_ROOT` when it is unset or empty (both `#[wire]`); `get_spec`, a tree's `TreeSpec` (sources' and subfields' trees, `SPEC_OFF_BY_DEFAULT`, allow specialization but open without it) |
| `src/components.rs` | Tree components (`DisJ`, `IntX`, `PostRefIterWrap`, `CountryInstsPost`); `StackBasis` folding |
| `src/prune.rs` | Tree result pruning: `prune` keeps the top `MAX_SIBLINGS` by links and by specialization per level, `prune_wide` keeps the whole first level up to `MAX_WIDE` leaves |
| `src/arr_ext.rs` | Array manipulation extensions |
| `src/test_utils.rs` | Test utilities (`#[cfg(test)]`) |

Key patterns: `BeS<M, E>` (Backend Selector) for flexible data loading; condvar-based
thread pool in `TreeRunManager`.

**Tree cache** — the on-disk `.zst` files under `<data>/cache/<root_type>/<eid>/` are the
single source of truth; there is no in-memory done-index and nothing to build at startup. A
tree build writes, per period, the pruned tree `<tid>/{pid}.zst` (plus `<tid>/shallow1-{pid}.zst`
when it is big) and the **first-level profile** `first/<entity>-<citing|refed>/{pid}.zst`: the
whole first level up to `MAX_WIDE` leaves, keyed by the level a `BreakdownSpec` names, so every
tree opening with that level reads and writes the one file (authors' citing-country trees, say)
and the `wide=` view and the share metrics read the same profile. Files are written beside their
target and renamed into place. A request first tries to read+decompress the file its `Serve`
mode names (success ⇒ serve). On miss, cacheable queries register in
`TreeBasisState::in_progress` (`CacheKey → BoolCvp`): the first claimant computes and writes all
period files; concurrent duplicates wait on the cvp, then re-try the read. The entry is removed
and waiters notified on every exit — including panics — via an RAII guard (`InProgressGuard`);
waiters hold their own `Arc` to the cvp, so immediate removal is safe. Non-cacheable
(sub-`CACHEABLE_FROM`) queries skip the registry entirely: no file will appear, so waiting
would only delay the recompute; they still serve a disk file if one exists (e.g. written before
a threshold change). `big_prep`/`big_read` are explicit compute commands and never serve from
cache.

### rankless_server — HTTP API server

Split by concern; `main.rs` holds only the allocator, module declarations, and route wiring.

| File | Role |
| --- | --- |
| `src/main.rs` | Allocator (mimalloc), module decls, `main`/`async_main`: the thread count (`RANKLESS_THREAD_COUNT`, else `DEFAULT_N_THREADS`) for the Tokio workers and the tree pool, `/v1` route table + socket bind on `PORT`; the static routers (`/counts`, `/specs` = `{version}`, the version stamp, `/columns` = the metric registry per root from `handlers::table::column_registry`, all serialized once at startup) |
| `src/consts.rs` | Server constants (`PORT`, `MAX_HITS`, `SEARCH_SIZE`, `MAX_SLICE`, `MAX_METRIC_IDS`, `MAX_METRIC_CALLS`, `MAX_PINS`, `SCREEN_K`, `COMMIT_HASH_LEN`, `CACHEABLE_FROM`, `DEFAULT_N_THREADS`, `N_SUBFIELDS`, the works-page and work-set intersection caps) + `FIN_*` showcase lists; `PORT`, `MAX_SLICE`, `MAX_METRIC_IDS`, `MAX_PINS`, `SCREEN_K` and `COMMIT_HASH_LEN` are `#[wire]` (`rankless_server/consts.{ts,py}`), so the frontend, `mcp_server` and `pyscripts` read them |
| `src/commit_hash_len.in` | The commit-hash length's one literal: `consts.rs` `include!`s it as `COMMIT_HASH_LEN`, and `build.rs` bakes the version stamp's hash at that length from the same file |
| `src/responses.rs` | `METHODOLOGY` (`#[wire]`: `rankless_rs::metrics::METHODOLOGY` — the work screen (its first year inclusive), the paper-score constants, `topN`, `hSince`, `ladderPctBands`, `minTopicScore`, `topHitPapers`, `specCorrRate` — plus the first and last year with yearly counts, `yearlyCounts`, and the methodology texts filled from them) and `TREE_SPECS` (`#[wire]`: every root type's trees and the year breaks, from `state::TreeRoots`), which the site and the MCP server import instead of fetching; wire/DTO + query-param structs (`SearchResult`, `ViewResult`, `PaperOut`, `EntityPeersResp`, `LadderResp`, `Resolve*`, `TableRow` = a search result + rank + `values` keyed by metric call, `SliceResp` = `{rows, meta}` with `SliceMeta` = cohort total + screened set size + column keys, `SliceQ` = `sort` call + `where` expression + `pin`, `MetricValuesQ`, …) |
| `src/state.rs` | The search side of a root type: `NameState` (the engine, the responses in citation order, `sem_to_dm` → dm id, `oa_to_rid`/`dm_to_rid` → response index, the `Orderings` — one response-id ordering per parameter-free global metric the root can read, built at startup by walking `METRICS` and reading each through `MetricDecl::read`, so the set follows the registry and a ranking can never use a different formula from the one it displays; citations are left out, the response array is already that ordering), the per-entity reads over `RootColumns` a view needs (`serializable_ext`, `start_year` = the first era year with a paper, `year_window` = the stats view's window moved into `ERA`, `hit_papers`; hero relations + co-author network rebuilt per view from the mmapped tables), `IsTop`, type aliases (`StatesT`, `InstTrm`, `NameStateMap`) |
| `src/cohort.rs` | Binding and evaluation against one root: `Ctx` (state + columns + getters + labels + tree specs; `registry()` = the metrics that exist for the root with their kind; `resolve` = a name to an id by semantic id, then case-insensitive label, cities by name), `bind_call` (arity + argument type; a year window only inside `ERA`, its first year first), `bind_where` (operator against value type, operands resolved to ids, a walk refused), `Bound::admits` (numbers compare, entity values match, a set-valued read matches on any / excludes on none), `Cohort` (fixed startup ordering, or a scan of the admitted ids kept with their sort keys; a per-entity sort or clause screens to the top `SCREEN_K` by citations after the global clauses, and per-entity clauses combine only under a top-level `and`; `columns` = the parameter-free globals, the sort's parameter family, every parameterized clause; `rank` by binary search) |
| `src/search_cache.rs` | On-disk cache for the per-entity `SearchEngine` (fnv64 content stamp, load/save) |
| `src/startup.rs` | Server bootstrap (`get_rest`): parallel per-entity state load (`para_multi_gen_run!`), node stats, `TreeRunManager` build; blanks the semantic id of every author in `author_blacklist.txt` as the authors state is built — the one point that removes the profile page, search hit, tree slices and top-list rows together while the name and papers stay everywhere else |
| `author_blacklist.txt` | OpenAlex ids that get no author profile — people who asked for theirs to go, plus the records where OpenAlex credits a country (or the UN) as the author of its own constitutions, legal codes and UN documents — `<oa_id> <name>` per line, `# cleared <oa_id> <name> — why` for a person who only shares a country's name; `include_str!`-embedded, so a change is a commit + rebuild + restart, no data or DB step; everything below the marker line is written by `pyscripts country-authors` |
| `src/util.rs` | Shared handler helpers (`cache_header`, `static_router`, `get_empty`, `resolve_dm`/`resolve_entity` = the etype + semantic id → state/dm id/response id path every entity handler takes; ids arrive decoded — a client encodes each once, axum's `Path` decodes it once) |
| `src/handlers/` | Axum handlers by concern: `search` (names/sem-id/orcid/resolve), `entity` (views/trees/ladder/tops + meta), `peers`, `works` (paper sets + DAG + CNF work-set intersection; a paper's `authorships` are its served rows in position order, `served_ships`: never an unresolved row on discarded author 0, and past `WORK_SCREEN.team_limit` rows only the first ones plus those of the requested authors and of laureates, while `authorCount` counts every row), `table` (`column_registry`, the per-root registry `/columns` serves, built once at startup; `/where?q=` = the parsed tree of an expression, `/slice?sort=<call>&where=<expr>&pin=` cohort pages as `{rows, meta}`, `meta` carrying the narrowed cohort's size, a screened ranking's set size and the rows' metric columns; `/metrics/:etype?ids=&metrics=<calls>` page-local values keyed by call, a walk metric answered from the tree pool) |

### Supporting crates

| Crate | Role |
| --- | --- |
| `dmove` / `dmove_macro` | Metaprogramming: generates entity/attribute/link Rust source tailored to dataset shape; `ByteFixArrayInterface::FITS_FIXBUF` fails the build (not `cargo check`) for a fixed attribute wider than `MAX_FIXBUF` (see [Metaprogramming](#metaprogramming--make-pipeline)) |
| `rankless_expr` | The table's expression language, depending on nothing else in the workspace: tokenizer + recursive-descent parser for `where` (clauses `call op value` under `and`/`or`/`not`/parentheses, precedence parentheses > not > and > or, `in (…)`), a single call (`sort=`) and a call list (`metrics=`); calls carry arguments (`field_score(oncology)`, `window_papers(2020, 2024)`), names are slugs or quoted strings in which `\X` is the character `X`; the tree serializes for `/where` and prints canonically (`Display`); every malformed input is a positioned error, and every input is bounded — `MAX_INPUT_BYTES`, `MAX_DEPTH`, `MAX_CLAUSES`, `MAX_LIST_ITEMS` — so nothing a request carries can drive the recursion into the stack's limit. Syntax only: binding is `rankless_server/src/cohort.rs` |
| `muwo_search` | Partial-string search engine for entity names: `lib.rs` (trie/engine), `io.rs` (serialization), `fixed_heap.rs`, `merging.rs`, `tests.rs` |
| `wiretypes` / `wiretypes_macro` | `#[wire]` on a Rust type derives its JSON Schema and registers it, and on a `const` or immutable `static` registers its value; `make types` renders every registered type, and every value as an `export const` (TS) or a `Final` (Python), into TS (`src/lib/wire/`) and Python (`wire/`), one file per Rust module (the constant modules: [Generated Python types](#generated-python-types-wire)), configured by `wiretypes.toml` (see [type-generation.md](type-generation.md)) |

### Svelte frontend (`src/`)

SvelteKit app; SSR via `+page.server.ts`; all visualizations hand-written SVG (Cytoscape.js
the only viz dependency).

**Types & constants**

| File | Role |
| --- | --- |
| `lib/wire/` | Generated (`make types`): the TS form of every `#[wire]` Rust type and constant, one file per Rust module (`rankless_server/responses.ts`, `rankless_server/consts.ts`, `rankless_trees/io.ts`, `rankless_rs/user_ledger.ts`, ...; the constant modules are listed under [Generated Python types](#generated-python-types-wire)) |
| `lib/tree-types.ts` | Frontend-only types: `TreeGen<T>` and the tree node shapes over the generated `CollapsedNodeJson`, `RootType`, `EntityType`, `RootedResult`, `NamedEntity`, control/selection specs |
| `lib/constants.ts` | `BE_URL` (the local backend on the generated `PORT`), `ENTITY_TYPES`, `MAX_LEVEL_COUNT`, `DEFAULT_LIMIT_N`, `BRAND_STATS`, ORCID endpoints; feature switches `EMAIL_FEATURE_ON` / `GAME_FEATURE_ON` / `MCP_FEATURE_ON` (see [unfinished-features.md](unfinished-features.md)) |
| `lib/paths.ts` | Where the user DB (`DB_REL`), the MCP object store (`MCP_OBJECTS_REL`), the user-ledger dir, the share-card cache and the survey log live, read from `assets/data/paths.json` like `pyscripts/paths.py`; free of SvelteKit virtual modules, so bun scripts import it too |
| `lib/assets/data/{paths,dev,game,card-style}.json` | Values Python and TS share that have no Rust source, each read by both sides: `paths.json` (the data locations above; `pyscripts/paths.py`, `lib/paths.ts`, `tests/e2e-env.ts`), `dev.json` (`devPort`, `previewPort` and the dev-login ORCID; `vite.config.ts`, the Playwright configs and helpers, `dev-login/`, `pyscripts/dev/_common.py`), `game.json` (the quiz's card kinds and options per card; `lib/utils/game-geo.ts`, `pyscripts/explore/game_card_mining.py`), `card-style.json` (the share-card raster size, accent and brand spectrum; `lib/utils/cards.ts`, `pyscripts/sharecard_test.py`, `pyscripts/poster_figures.py`); Python loads them through `paths.asset()`. The card contract `card-kinds.json` is shared the same way (`lib/server/cards/kind.ts`, `mcp_server/cards.py`) |
| `lib/v_constants.ts` | `VERSION`, `LAST_MOD` build-time info |
| `lib/types.ts` | `SurveySubmit`, `SurveyRecord` |
| `lib/types/showcase.ts` | `ShowcaseData` and parts — shape of the baked `homepage-showcase.json` consumed by `FeatureShowcase.svelte` |
| `lib/types/release-report.ts` | `ReleaseReport` and parts — shape of the baked `release-report.json` (`pyscripts/release_report.py`) rendered at `/release` |
| `lib/types/review.ts` | Ledger-review types: `WorkRecord`/`OrcidRecord` (enrichment cache), `ReviewVerdict`, `AdminReviewRow`; mirrors `pyscripts/review_ledger.py` |

**Utility modules**

| File | Role |
| --- | --- |
| `lib/tree-functions.ts` | Tree traversal/flattening/filtering; `getDefaultBreakdowns()`, `getBreakdownOptions()`; `getDefaultYear(rt)`, the year a root type's tree opens on, one of `TREE_SPECS.yearBreaks`: the first, which keeps the whole record, or a recent one for countries and subfields |
| `lib/tree-events.ts` | Click/hover/selection handlers |
| `lib/visual-util.ts` | `rescale()`, `getSankeyPath()`, `pinRange()` |
| `lib/metric-calculation.ts` | `getSpecMetricObject`: a tree node's specialization, its rate against the served `specBaseline` |
| `lib/table-utils.ts` | Browse-table model over the `/columns` registry: which metrics rank (`rankable`), narrow (`clauseable`) or make page-local columns (`annotatable`), the call spelling shared with the backend (`callText`/`parseCall`), `where` chips ↔ text (`chipsFrom`/`whereText`/`chipLabel`), column names from header templates (`columnLabel`), formatting by value type, page-local stable sort, `argsReady` (every argument the parameter takes is given; what they say is the backend's to check) and `defaultArgs` (a window starts on the last `DEFAULT_WINDOW_YEARS` served yearly-count years), and the fetchers (`fetchSlice` and `fetchColumnValues` returning the backend's error text beside the data, `fetchWhere`); the table page and the table card load a cohort through the same pieces (`fetchRegistry`, `tableQuery`, `fetchCohort` for the page and the pinned rows, `fetchParamEntities` for the fields and countries an argument names, `columnOf`, and `sortColumn`, which reads the ranked column under the backend's own spelling of the call) |
| `lib/network-util.ts` | Co-authorship graph utilities (light layouts); `COOLING`, the force layout's cooling schedule: the layout's defaults and where the tuning sliders start |
| `lib/utils/author-timeline.ts` | Aggregates co-authors from the full loaded works into per-year, span-bounded rows (`buildCoauthors`/`sortCoauthors`/`coauthorYearDomain`/`makeTicks`) for `AuthorTimeline` and the timeline card |
| `lib/utils/cards.ts` | What every share card shares: the geometry (`CARD_W`×`CARD_H`, the raster size social platforms take, with the accent and the brand spectrum read from `card-style.json`) and the frame's inner box, the brand faces with their average advances, the literal colours, and the text fitting done by character count (`fitSize`, `labelSize` under `LABEL_FLOOR`, `clipToWidth`, `wrapLines`, `gutterWidth`), since the rasterizer resolves neither CSS variables nor scoped styles and nothing can be measured |
| `lib/utils/composite.ts` | Geometry and panel addressing of a composite card: `MIN_PANELS`/`MAX_PANELS`, `compositeLayout` (panels in rows of one to `MAX_COLS` columns — by default one column at `MIN_PANELS`, `MAX_COLS` above it — each in the box its own card draws it in, a short last row centred), `parsePanelRef` (a panel is a card's path and variant, `<type>/<semantic id>/<kind>?<query>`) and `namespaceIds` (a panel's SVG ids and their references prefixed, since ids are global to the document) |
| `lib/utils/year-ticks.ts` | The yearly chart's pure pieces shared by `YearTicks` and the yearly and peers cards: `niceTicks`, `tickCount`, `countGrid` (the labelled gridlines of a bar span), `seriesYears`, and `compactCount` (a count to three significant digits with its unit) |
| `lib/utils/flat-out-styles.ts` | The map's and the research space's pure scaling shared by `WorldMapSvg`/`ConceptMap` (which write it as CSS variables) and the map/fields cards (which write it as attributes): `countryStyles` (fill, opacity and breakpoint bucket per country), `subfieldStyles` (radius and saturation per field), the domain colour order and the per-root-type semantics of both breakdowns |
| `lib/utils/flat-out-cards.ts` | Layout of the map and fields cards over `flat-out-styles`: the candidate spots of each label (placed by `label-placement`), legends, the props types |
| `lib/utils/label-placement.ts` | The greedy label placement the map, fields and network cards share: `placeGreedy` (each label takes its first candidate box clear of the placed ones and of its blockers; a must-draw label is never dropped) and `overlaps` |
| `lib/utils/paper-rainbow.ts` | The hit-paper rainbow's chart math shared by `PaperRainbow`, `ShowcaseRainbow` and the papers card: `rainbowPapers` (filter + sort), `computeYearRates`, `getFigureBasis` (cumulative trajectories, ticks, marks), `tipLabelPos` |
| `lib/utils/impact-card.ts` | Layout of the impact card: chip widths from the text estimate, `uncross` (the row order with the fewest crossing edges) |
| `lib/network-force.ts` | Cytoscape/fcose force layout — lazily imported so the vendor chunk stays off initial load |
| `lib/route-functions.ts` | URL builders |
| `lib/loading-functions.ts` | Data fetching orchestration: `loadTops`, `TopTreeLoader` (the homepage's random top tree) |
| `lib/text-format-util.ts` | Number/text formatting; `semantify` + `SEM_MAP` (see [breakdown selection](#breakdown-selection)) |
| `lib/style-util.ts` | CSS/SVG styling |
| `lib/stores.ts` | Svelte reactive stores; the localStorage-backed top-paper cache (`prefetchPaper`, which settles every waiter even when the OpenAlex load fails) |
| `lib/sitemap-functions.ts` | SEO sitemap helpers |
| `lib/util.ts` | General utilities |
| `lib/utils/ledger-effective.ts` | Derives effective disowned/ledger sets for `AllWorks` from applied + pending events |
| `lib/utils/works-loader.ts` | Shared paginated author-works store (`createWorksLoader`); one instance per hero page feeds both `AllWorks` and `AuthorNetwork` so works are fetched once; the page URL, page size and merge (`worksPageUrl`, `WORKS_PAGE_SIZE`, `mergeWorks`) are the timeline card's too |
| `lib/utils/works-paging.ts` | How an author's works are paged from the backend (`INITIAL_PAGE_SIZE` for the server-seeded first page, `WORKS_PAGE_SIZE`, `WORKS_SORT`), read by `works-loader`, the entity page's load, the timeline card and the ledger spec; free of SvelteKit virtual modules so Playwright imports it |
| `lib/utils/ledger-queue.ts` | `QUEUE_PER_CHOICES`/`QUEUE_PER_DEFAULT`: the rows per page the `/admin/ledger` queue offers, read by `LedgerQueueFilters` and the page's load, which clamps `per` to their range |
| `lib/utils/stale-guard.ts` | `createStaleGuard`: `claim()` marks a new in-flight op and returns `isCurrent()`; every entity-page fetch drops a superseded response through it |
| `lib/utils/tree-loader.ts` | `createTreeLoader`: `load(conf, shallow?)` resolves to the tree only while still the newest request; `$state` = conf/resp/loading; one per `FullQc`/`FlatOutFrame` |
| `lib/utils/works-intersection.ts` | `fetchWorkIntersection`: encodes a CNF `WorkSetQuery` (`$lib/types/work-set.ts`) into the `/works-intersect/*spec` path and returns a `PaginatedPaperSetResp` |
| `lib/hero-config.ts` | Per-root-type `HERO_CONFIG` + chip/leader/field-topic builders for `EntityHero` (stat, badge policy, leaders, topics nested under their parent field) |

**Routes**

| Route | Role |
| --- | --- |
| `(stat)/` | Home; top entity lists |
| `(stat)/[rootType]/[...semanticId]/` | Entity hero page (tree + network + map; ledger panel for owners) |
| `(stat)/[rootType]/table/` | Browse table: the cohort of a root type ranked by a metric call chosen in the Metrics block (a per-entity metric ranks the top `SCREEN_K` by citations, the cohort note and group header saying so) and narrowed by a `where` expression built in the Filter block (`ClauseBuilder`: one clause at a time as chips; an expression the chips cannot show is edited as text; the backend's objection is shown under the note); the columns are what the page's `meta.columns` lists, `#` = rank in the narrowed cohort, the standing tier from the cached ladder when a field metric is in play; entities pinned by name (`pin=`) ahead of the ranked rows; a header click sorts the loaded rows only; page-local columns for further calls fetched in one `/metrics/:etype` call per column and page, cells reading "…" while in flight; a root-type switcher heads the page, and the cohort note also names the papers the metrics count, read out from the served work screen (`workScreenPhrase`, the same words as the indexed-citation explainer and the FAQ); each column's info gives the years it covers. Composed of `MetricPicker`, `ClauseBuilder`, `ParamInputs` and `EntityPins` |
| `(stat)/about/`, `(stat)/survey/`, `(stat)/privacy/` | About / survey / privacy notice |
| `(stat)/release/` | Data-release report (baked `release-report.json`; see [deploy.md](deploy.md)) |
| `(stat)/login/`, `(stat)/logout/`, `callback/`, `dev-login/` | ORCID OAuth + dev bypass |
| `api/ledger/`, `api/ledger/[event_id]/`, `api/ledger/[event_id]/revoke/`, `api/ledger-status/` | Ledger CRUD + status |
| `(stat)/admin/`, `(stat)/admin/ledger/`, `(stat)/admin/games/` | Admin overview (users + consents) / ledger review queue (see [ledger-review.md](ledger-review.md)) / games admin: per-kind pack counts + the run count, and `admin/games/cards` reviews every card of every kind on one page (question, answer, other options, badges, reveal text, reproduced-facts tally) with the same approve/reject-with-note flow as `/mcp` |
| `(stat)/mcp/` | MCP docs: connect-your-agent snippets, tools, resources and prompts from the baked manifest (docs/mcp-server.md) |
| `api/admin/moderate/`, `api/admin/enrich/` | Bulk approve/reject; chunked external-metadata fetch + hard-evidence auto-accept |
| `(stat)/email-preferences/`, `api/email-consent/` | Opt-in email consent form + API (gated by `EMAIL_FEATURE_ON` in `lib/constants.ts`) |
| `api/papers/{disown,claim,merge}/`, `api/authors/merge-request/` | Legacy paper/author actions (forward to ledger; slated for removal) |
| `tiles/[rootType]/[...semanticId]/` | Treemap visualization |
| `(stat)/game/` | Games hub linking CampusQuest (also keeps pre-split `/game` share links working); the footer link to it is gated by `GAME_FEATURE_ON` |
| `(game)/[game=campusQuest]/`, `api/game-geo/` | "CampusQuest" geography quiz (served at `PATH`: the route directory matches on the `SLUG` constant via `src/params/campusQuest.ts`, so renaming the game is one string) over one object kind per question pair (where an institution actually is, which institution is not in a country, which is closest to one, which city one is in, which is in a city — the kinds are `game.json`'s, the question each asks is `QUESTIONS` in `lib/utils/game-geo.ts`, and the pair on screen is the instruction). `OPTIONS_PER_CARD` tappable options per card (`game.json`), `RUN_SECONDS` each, every answer holds its reveal in a bottom sheet under a ✓/✗ verdict — the answer, and under it where it sits against the question: the intruder's real city and country with its flag, the nearest option's distance, otherwise the prompt (a nearest reveal draws the options around the prompt on `GameMap`); the intruder question stresses its "not"; long option names step down in size instead of clipping. The daily is the same `DAILY_SIZE` cards for everyone (the fixed kind recipe `DAILY_RECIPE` over the day's hash order, the kinds interleaved so the opening cards are all different and a short kind filled from the kind dealt least, ships with the page), no death, one 50:50 lifeline per card, a hit after it scoring `HALF` instead of `FULL` (the clock restarts); the result screen shows the score in half-points, a 🟩🟨🟥 share grid, the misses with their answers, the day's standing and a stats sheet over the browser-kept history. Survival (GET a shuffled whole pack) keeps `LIVES` lives and no lifeline. Runs POST into `geo_game_runs` (score in half-points, deck size, missed + lifelined anchor sem-ids) and get the day's standing back; full-viewport phone-first layout outside the `(stat)` chrome |
| `path-to-person/[aidSrc]/[aidTarget]/` | Collaboration path finder (built; not linked from live nav — see `unfinished-features.md`) |
| `oa-id/[oaId]/` | OpenAlex ID → entity redirect |
| `api/survey/`, `card/[rootType]/[...semanticId]/[kind].[ext=cardext]/`, `card/composite.[ext=cardext]/`, `card/home.png/`, `sitemap*.xml/`, `robots.txt/` | Survey / the share cards (every kind of an entity or a cohort as SVG or rasterized PNG, see `lib/server/cards/`; the entity page's `og:image` is its `tree.png`), the composite of several cards, and the homepage OG card / SEO |

**Key components**

| Component | Role |
| --- | --- |
| `TreeSvg.svelte` | Main hierarchical breakdown tree |
| `ConceptMap.svelte` | Research-space field network |
| `AuthorNetwork.svelte` | Co-author panel hosting a network/timeline tab toggle. Network: co-authorship graph (Cytoscape); click a node/edge to browse the team papers (`isTeamPaper`, the only ones that make co-authors) shared with that co-author (or both) via the shared `works-loader`. On an edge whose hero-three-way set is empty, offers the pair's own two-way intersection via `works-intersection.ts`. Switching to timeline triggers `works.loadAll()` |
| `AuthorTimeline.svelte` | Band-style co-author timeline (every named collaborator on the full work set's served authorships, incl. unlinkable discarded authors): per-row span bar + per-year marks, hit highlighting, hover tooltip, min-shared-papers + sort controls; built from `lib/utils/author-timeline.ts` |
| `WorldMapSvg.svelte` | Geographical citation impact map |
| `GameShell.svelte` | Centered-card frame for the games hub: title header + the `.intro` chrome |
| `GameFrame.svelte` | Full-viewport (100svh, no scroll) phone-first frame for the arcade games (`/campus-quest`, the ranking game next): hub link + mode label + streak header, plus shared `:global` chrome — the palette-ramp bar (`.ramp-bar`), big buttons (`.g-btn`), status-colored hearts (`.hearts`), the bottom sheet (`.sheet`) that holds a reveal or a stats panel, and the `--game-sub` sub-label color |
| `GameStats.svelte` | Personal stats body for the quiz's stats sheet: played / best / average / streak tiles plus a per-point score histogram over the browser-kept daily history (`runStats`), nothing server-side |
| `GameMap.svelte` | Reveal map for the nearest cards: the prompt institution (labelled) and its options on the country-paths asset, zoomed to the points with a floor so a cluster of campuses stays apart (Robinson projection from `map-projection.json`, fit by `pyscripts/calibrate_map.py`), strokes, markers and type sized against the frame, labels placed beside their marker on the side with room and stepped apart, dashed ties and the nearest highlighted |
| `TileTreeMap.svelte` | Treemap view |
| `PaperRainbow.svelte` | Hit-paper citation area chart with scrollable list |
| `HitPaperBreakdown.svelte` | Lazy citation breakdown for a single hit paper |
| `ImpactDag.svelte` / `DagChip.svelte` | Citation impact DAG + paper chips |
| `AllWorks.svelte` | Paginated author paper list (reads the shared `works-loader`); ledger/disown UI |
| `AuthorLedgerPanel.svelte` | Owner's profile-changes panel (applied/pending events) |
| `AuthorOwnerTools.svelte` | Legacy owner action UI (slated for removal) |
| `ExportControls.svelte` | Sort/filter/citation-style/BibTeX controls |
| `EntityHero.svelte` | Hero-page header, config-driven per root type (`$lib/hero-config.ts`): per-entity stat, specialization field chips (standing badge except countries) that nest each field's top topics, tailored leader rows, decade chart |
| `ProfileDisclaimer.svelte` | A profile's disclaimer: a bordered "Data note" across the bottom of an entity page's first card |
| `InfoTip.svelte` | Unified "what is this?" tooltip: small `i` badge (or inline-text) trigger, opens on hover/focus/tap, solid background positioned at the trigger and clamped to the viewport. Used by `IndexedCitationLink`, `HeadControl` (Specialization / since-year), `HeroFieldBlocks` (papers-in note), `AxesOfFocusReach`, the browse table's column headers |
| `IndexedCitationLink.svelte` | "indexed" citation explainer (wraps `InfoTip`; shared across stat-line variants), rendered from the served work screen |
| `Peers.svelte` / `BarChart.svelte` | Peer comparison bars + shared span-bar chart |
| `DominatedTopics.svelte` | "Topic Leadership" list (entity's dominated topics) |
| `WorkElem.svelte`, `SearchResults.svelte` | Single paper / search autocomplete |
| `ScrollyGraph.svelte` / `ScrollySank.svelte` / `TimelineViz.svelte` | Scrollytelling + timeline viz |
| `PathLevelInfoBox.svelte` / `MidpathBar.svelte` | Path UI |
| `MetricPicker.svelte` | Browse-table metric picker, used for the ranking and for page-local columns: a metric and the argument its parameter takes (through `ParamInputs`), handed over as a call; applied at once when parameter-free, with the button otherwise |
| `ParamInputs.svelte` | The inputs of a metric's parameter — a field, a country, a year window — bound to the call's arguments, the year inputs bounded by the served yearly counts and each other (`:invalid` marks a year outside them); shared by the picker and the clause builder |
| `ClauseBuilder.svelte` | Browse-table narrowing: a metric call, an operator its value type allows and an operand (a number, a country, a typed name) make one clause of the `where` conjunction, each a chip; any other expression shape is edited as text and applied whole |
| `EntityPins.svelte` | Browse-table pins: `PeerSearch` by name adds an entity, chips (named by the pinned rows) remove one; the page carries the pins in `pin=` |
| `HeadControl.svelte`, `Toc.svelte`, `FlatOutFrame.svelte` | Header / sticky nav / flat-view frame (own `tree-loader`; hosts bind `treeId`, keyed on entity identity by the page) |
| `FeatureShowcase.svelte` | Homepage "Latest features" section: per-feature cards (Login, Hit-papers, Co-author timeline, Peers, Co-authors; All works + export demoted to the text-only "And more" grid). Reads the baked `homepage-showcase.json` (zero backend calls on load); composes the four data previews below |
| `ShowcaseRainbow.svelte` / `ShowcaseTimeline.svelte` / `ShowcasePeers.svelte` / `ShowcaseCoauthors.svelte` | Static, real-data previews for the showcase: a mini hit-paper rainbow (arcs by citations); a compact co-author timeline (spans + per-year marks, hit-flagged); a hero-vs-peer comparative bar pair (by field + by year); a ring-layout co-author mini network (no Cytoscape) |
| `cards/CardFrame.svelte` | The one frame around every share card: the entity's name, a caption saying what the picture shows, the visualization in the inner box, the wordmark and the URL; pure SVG in the brand faces, literal colours |
| `cards/CompositeFrame.svelte` | The frame of a composite: one large title, each panel's heading over its kind's rendered SVG, the wordmark and the URL, the title and mark scaled with the canvas |
| `cards/{Yearly,Map,Fields,Timeline,Network,Papers,Impact,Peers,Table}Card.svelte` | One pure-SVG component per card kind (the tree kind renders `TreeSvg` itself): no `<style>`, no CSS variables, no measurement, labels dropped under the floor rather than shrunk, the highlighted item always labelled with its value |
| `cards/GridLines.svelte`, `cards/CardLabels.svelte` | The dashed, labelled gridlines of the yearly and peers cards; the haloed name-and-value labels of the map and fields cards |
| `HomeCard.svelte` | Brand homepage OG card (wordmark, tagline, live `/counts` figures followed by `BRAND_STATS`, the qualitative proof-point that needs no data and shows alone when that fetch fails, spectrum breakdown bar); typeset in the revamp faces — Hedvig Letters Serif/Sans + Space Mono, vendored in `static/fonts/` and installed into the runner's fontconfig by `deploy.py` so `rsvg-convert` uses them. Server-rendered to standalone SVG (no `<style>`/CSS vars), rasterized via `card/home.png` |

| `LedgerClaimantGroup.svelte` / `LedgerEventRow.svelte` / `LedgerQueueFilters.svelte` / `VerdictBadge.svelte` / `OrcidLink.svelte` | `/admin/ledger` review queue: per-claimant collapsible batches, enriched event rows (DOI/OpenAlex links, auto/proven badges, expandable AI verdicts), URL-driven filters + pager |

**Server utilities**

| File | Role |
| --- | --- |
| `lib/server/session.ts` | ORCID session management |
| `lib/server/db.ts` | SQLite singleton (`bun:sqlite`, WAL) at `RANKLESS_DB_PATH`, else `DB_REL` from `lib/paths.ts`; ledger + review tables (`subject_enrichment`, `review_verdicts`) |
| `lib/server/render.ts` | `renderSvgComponent` — Svelte 5 `svelte/server` `render()` to HTML string |
| `lib/server/cards/index.ts` | The share-card registry (`CARD_KINDS`, one loader per kind of the contract; a kind the contract does not name, or one the entity type lacks, is a 404 before any backend call), `loadCard` (the entity's `/views` profile → the kind's `load`: what a frame draws), `buildCardSvg` (`CardFrame` around it, rendered with `svelte/server`), `cardPng` (disk cache → render → `rsvg-convert`) and the PNG/SVG responses shared by `card/…` |
| `lib/server/cards/composite.ts` | `/card/composite.png?p=<panel>&p=<panel>&cols=`: `MIN_PANELS` to `MAX_PANELS` cards (`lib/utils/composite.ts`) merged into one picture, each `p` loaded through `loadCard` exactly as its own card is, titled with the names of the entities shown; rendered per request with no disk cache (a post bundles the file once) |
| `lib/server/cards/kind.ts` | `CARD_SPEC`, the card contract read from `lib/assets/data/card-kinds.json` (every kind's entity types and variant parameters with their defaults and limits; `mcp_server/cards.py` reads the same file), the loader contract (`CardKind = { component, load(ctx) }`, `CardContext` with the profile and the variant parameters, `CardData`), the variant-parameter parsers (ids, years, counts, fixed words; anything else is a 404, never free text), `beJson` (a backend failure is a 404, never a 500) and the caption words per entity type |
| `lib/server/cards/{tree,yearly,map,fields,timeline,network,papers,impact,peers,table}.ts` | One loader per kind: the variant parameters parsed by the contract's defaults and limits, the backend calls, the props and the caption (`network.ts` also lays its ring out); `flat-out.ts` (`loadFlatOut`) loads the level-1 weights the map and fields kinds share; `home.ts` renders the homepage card from live `/counts` |
| `lib/server/cards/works.ts` | `loadAllWorks`: every page of an author's works for the timeline card, over `works-loader`'s URL and merge |
| `lib/server/card-raster.ts` | `rsvg-convert` rasterizer + best-effort disk cache for the share cards (`CARD_CACHE_DIR`, else `CARD_CACHE_NAME` from `lib/paths.ts` under the OS temp dir) |
| `lib/server/survey-cookie.ts` | `setSurveyCookie`: marks the survey answered or dismissed so the visitor is not prompted again, shared by `api/survey/` and its `reject/` |
| `lib/server/id_resolver.ts` | Resolves UI entity refs to stable-ID payload blocks |
| `lib/server/ledger-hash.ts` | `subject_hash` computation for ledger dedup |
| `lib/server/enrich.ts` | Pure fetch+pluck of Crossref/OpenAlex work + ORCID person records (the app's only external-metadata fetcher) |
| `lib/server/review.ts` | Pure review-domain logic: DOI/ORCID canonicalization, hard-evidence rule, verdict picking, `AdminReviewRow` composition |
| `lib/server/review-data.ts` | DB glue: `runEnrichment` (chunked cache fill + auto-accept), `loadReviewQueuePage` |
| `lib/utils/reference-format.ts` | Academic reference formatting (APA/MLA/Chicago, BibTeX) |
| `lib/utils/paper-helpers.ts` | Paper/author/source name resolution (an authorship without a name is left out; `authorByline` caps the named authors and counts the rest of `authorCount` as "+N others" for `AuthorList.svelte`); highlight detection; OpenAlex work payloads (`fetchOaJson` bounds the wait and checks the status, `oaWorkToPaperResp` tolerates the nulls the API allows) |
| `lib/server/disclaimers.ts` | `activeDisclaimer`: a profile's `profile_disclaimers` row, returned only while its `run_id` is the ledger manifest's, so a note lapses with the data run it was written against; the manifest is read only for a profile that has a row |
| `lib/utils/dag-builder.ts` | DAG construction from RefTree |
| `lib/utils/impact-summary.ts` | Summary counts (Nobel, Science/Nature, standout) for citing papers, and the phrases the page and the impact card word them with |
| `lib/utils/clipboard-download.ts` | Clipboard copy + file download |
| `lib/utils/game.ts` | Shared game plumbing: day stamp, streak rule, FNV hash, shuffle, flags + `Intl` country names, share-text frame, localStorage state, result-POST + clipboard helpers |
| `lib/utils/geo.ts` | The world-map asset's lat/lon→map projection over `map-projection.json` |
| `lib/utils/game-map.ts` | Layout of the nearest reveal map: the frame around the marks (padded, aspect-locked, a floor so a campus cluster stays apart) and label placement beside each mark, sized against the frame; unit-tested on real card geometry |
| `lib/utils/game-geo.ts` | Quiz rules: the public identity (`BRAND`/`SLUG`/`PATH` — the single source of truth the route matcher, links, share lines and specs read), the card kinds (`KINDS`) and the options on every card (`OPTIONS_PER_CARD`), both read from `game.json`, which the card miner reads too, the question each kind asks (`QUESTIONS`), the daily recipe (`DAILY_RECIPE`, kinds in a fixed order, short kinds filled from the others), survival lives, the question timer (`RUN_SECONDS`), the 50:50 (`lifelineKeep`, hashed per day) and half-point scoring (`FULL`/`HALF`, `points`, `formatPoints`), the share grid, deck builds (daily = rendezvous hash order by day + card id so everyone gets the same deck and a mid-day pack change shifts one slot of a kind at most, at most `MAX_MEDICAL_CARDS` hospital names; survival = the whole pack shuffled), verdict line, personal stats math (types in `lib/types/game-geo.ts`) |
| `lib/server/game-common.ts` | Shared server plumbing for the games: boundary validators, capped JSON body reader |
| `lib/server/game-geo.ts` | Server side of the quiz: pack reads over every card kind, `toPlayCard` folding each kind's stored payload into the one play shape (prompt, option keys + labels, the answer recomputed from the stored evidence), serve-time badge enrichment for country cards (top-percentile subfield standings from `/peers` + `/ladder` with the hero's own peers-utils machinery, cached per process; a country card without a standing never serves, the generated kinds show none), daily / survival deck serving, `geo_game_runs` run log that answers a daily run's standing + boundary validation |
| `lib/server/objects.ts` | Read/review access to the MCP object store (index rows + cached zstd bundle reads; written by pyscripts, see [mcp-server.md](mcp-server.md)): the quiz (`PATH`) consumes current cards of every kind, `/admin/games/cards` reviews them; SQL shared with the e2e seeder via `objects-schema.ts` |
| `params/campusQuest.ts` | Route param matcher for the quiz: matches the one `SLUG` from `lib/utils/game-geo.ts`, keeping the brand out of the route directory name |
| `params/cardext.ts` | Route param matcher for a share card's extension: `png` or `svg` |
| `hooks.server.ts` | SvelteKit middleware |

### Python scripts (`pyscripts/`)

| File | Role |
| --- | --- |
| `__main__.py` | Unified CLI (`uv run -m pyscripts <command>`): a `protocli` Dispatcher over lazily-imported command modules — a module exposes a typed `main(...)` (its signature is the parser) or a nested `_dispatcher`; `--help-all` prints every parser |
| `cache_prompting.py` | Query infrastructure: `BatchRequester` (trees from `TREE_SPECS`, after `wait_for_backend`), `get_resdf`, URL gen; `addr` configurable |
| `server_ops.py` | `ServerProcess`, `DockerServer`/`FlaskPgServer`, self-healing `build_image()`, `build_server()`, `current_branch()`, `checkout()` |
| `stow_ops.py` | `StowManager` (rsync stash per branch), `RebuildLevel` |
| `bm.py` | Benchmark suite: latency/throughput/memory across branches |
| `branch_comparison.py` | Branch-to-branch structural diff + timing (see [benchmarking](benchmarking.md)) |
| `sql_comparison.py` | Flask/PostgreSQL vs Rust diff + benchmark; two Docker containers |
| `comparison_driver.py` | Shared comparison skeleton: `prepare_backend`, `sample_entities`, `run_query_loop`, `write_artifacts` |
| `tree_diff.py` | Structural diff primitives: `flatten_tree`, `make_diff_df`, `metric_stats`, `top_source_stats` |
| `comparison_report.py` | Shared report generation: `CompResult`, summary/grouped DFs, plots, md/HTML |
| `poster_figures.py` | Brand-palette SVG/PDF figures from a run's CSVs for the ICWE poster (see `logs/POSTER.md`) |
| `export_user_ledger.py` | Exports SQLite ledger → a snapshot in the user-ledger dir under `$OA_ROOT` before `filter` (`ACTIVE_JSONL`, `SNAPSHOT_MANIFEST`, `OWNER_PINS`, the generated `user_ledger` names), the events whose moderation is `OK_MODERATION`; stamps each event's merge-stable logical key (`orcid\|kind\|subject_hash`) and resolves revokes away; copies the curated ledger (`CURATED_JSONL` in the external data root's `ledger/`) beside it under the same name, counted under `sources` |
| `ledger_ids.py` | Python side of the ledger's identifier + subject-key rules (canonical DOI/ORCID, subject builders over the generated `WorkSubject`/`AuthorSubject`, `subject_hash` for every kind the pipeline reads, `curated_line` for a whole curated-ledger line), the moderation states an event leaves the site in (`OK_MODERATION`, with its SQL clause `OK_MODERATION_SQL`) and the `subject_enrichment` sources that carry a work's authorship, in preference order (`WORK_SOURCES`) — one mirror of `src/lib/utils/identifiers.ts`, `src/lib/server/ledger-hash.ts` and `rankless_rs/src/user_ledger.rs` for everything that writes ledger rows from Python |
| `claims.py` | Paper-claim release lane (`uv run -m pyscripts claims <step>`): `review-merges` (y/n per name-matched candidate, decision written back into the plan), `apply-merges`, `accept` (only what the snapshot proves; stamped `auto:snapshot-authorship`), `record` (the release's `releases/<run_id>.claims.json` sidecar — publishable aggregates at the top level, per-claim detail under `detail`, which never leaves the box). Every case-specific decision lives in the per-release plan file, never in the repo |
| `review_ledger.py` | AI review lane (`uv run -m pyscripts review-ledger`): per-claimant agentic sessions (explore/runner.py engines + rankless MCP) over the `subject_enrichment` evidence bundles → structured `review_verdicts` for `/admin/ledger`; see [ledger-review.md](ledger-review.md) |
| `country_authors.py` | Country-vs-person verdicts for the author blacklist (`uv run -m pyscripts country-authors scan` / `review`): matches every author display name against the app's own country names, reports what the file leaves undecided, and shows an undecided record's papers before writing the verdict back |
| `disclaimers.py` | Profile disclaimers (`uv run -m pyscripts disclaimers add`/`remove`/`list`), run on the serving box: `add` checks the profile against the box's backend, stamps the row with the run id of `APPLIED_MANIFEST` in the user-ledger dir and replaces the profile's current note; `list` marks each row shown or lapsed. The table (`profile_disclaimers`, DDL mirrored in `lib/server/db.ts`) moves between boxes with the user DB (`userdb.py` `TABLES`) |
| `external_data.py` | The external-data root (`$EXTERNAL_DATA_ROOT`, `DEFAULT_EXTERNAL_DATA_ROOT` when unset, both from the generated `derived_ledger` module; a directory per source, outside the repo, the snapshot and `OA_ROOT`, never published): `source_dir`; `raw_dir`, a source's `raw/`, where a download the box can fetch again from its URL sits (`fetched` downloads a table there once); `table` for a table the pipeline reads (required once the variable names the root, optional under the default); and `push`/`pull` of the root with `$EXTERNAL_DATA_REMOTE` (`make external-push` / `external-pull`, additive rsync that never carries a `raw/`); stdlib-only |
| `orcid_summaries.py` | The ORCID Public Data File summaries reduced to the two tables Rankless reads (`make orcid_summaries`, once per yearly file): downloads the tarball into the `raw/` of the source directory `NAMES_TABLE` names under `$EXTERNAL_DATA_ROOT` (resumable, md5-checked), streams it once and writes there the registered-name table at `NAMES_TABLE` (orcid, given names, family name, credit name, other names — what `derive-ledger` reads), the public emails (`EMAILS_NAME`, every public email with primary/verified flags) and the pass's counts (`STATS_NAME`) |
| `deploy.py` | Application/box deploy: EC2 primitives (Nginx, systemd, SSL, code push, user-DB handoff) + ship_alpha/promote with smoke checks (`uv run -m pyscripts deploy <action>`); data pushes share the fleet's `manifest.push_data` definition, code deploys run `migration_scripts/` before the build, ship/promote refuse on a host whose DB holds no users or whose tree still holds a catch-up script, and on a backend port not owned by `rankless-server` (`listeners()` over `ss -lntp`) |
| `recalc.py` | Data recalculation stages: refresh-data, commit-artifacts, warm-caches (`uv run -m pyscripts recalc <stage>`, see [deploy](deploy.md)); ship_alpha/promote live in `deploy.py` |
| `release_report.py` | Pure release-record → public report derivation; bakes `src/lib/assets/data/release-report.json` (rendered at `/release`), `--md` promo digest, and the promote gate's report↔served-version assert |
| `cohort_baseline.py` | Snapshots each pinned owner's served works/citations to `$OA_ROOT/releases/<run_id>.cohort.json` while a release is live — the release-over-release attribution baseline |
| `gitutil.py` | Shared local-git plumbing (`git`/`git_out`/`git_lines`, `current_branch`, `head_commit` + `HEAD_CMD`, the hash at the generated `COMMIT_HASH_LEN` that `build.rs` bakes too, `assert_pushed`) used by recalc/deploy/fleet |
| `paths.py` | Repo-relative data locations shared across the ops scripts (`services.py` renders them into units, `deploy.py` moves them between boxes): the names the site shares (`DB_REL`, `MCP_OBJECTS_REL`, `USER_LEDGER_DIR`, `CARD_CACHE_NAME`, `SURVEY_LOG_PATH`) read from `paths.json` through `asset()`, which loads the other shared JSON assets for every script; `db_path()`/`objects_root()` with their env overrides (`RANKLESS_DB_PATH`, `MCP_OBJECTS_ROOT`); `ZSTD_LEVEL`, the level archives are written at; `GEN_DIR`, and `LADDER_TOP`, its last generated file, whose forced make rebuilds the whole pipeline; stdlib-only |
| `hosts.py` | The public hostnames of the site and its backends (`ALPHA_DOMAIN`, `LIVE_DOMAIN`, `ALPHA_BACKEND`, `LIVE_BACKEND`), derived from `mcp_server`'s `MAIN_DOMAIN` and `BACKENDS`, with no cloud dependencies, so `deploy.py`, `stress.py`, `sitemap_validation.py` and the reporting read them |
| `fleet/` (`config`, `remote`, `manifest`, `preflight`, `drive`, `calibrate`) | Cache-warm worker fleet over the machine-local `data/warm.toml`: validated band config, ssh/rsync transport, data manifest + stamp, preflight invariant gate, phased driver (prepare → gate → compute → coverage gate), probe/suggest calibration helper, standalone `prepare` (converge + gate, no compute) (`make fleet-<action>`) |
| `live_monitoring.py` | Health monitoring + email alerts |
| `make_test_dataset.py`, `lib_data_generation.py` | nano/micro/mini subset generation |
| `homepage_showcase.py` | Bakes `src/lib/assets/data/homepage-showcase.json` (one featured scholar's hit papers, co-author timeline, hero-vs-peer comparison, and co-author network) for the homepage showcase; run via `make homepage_showcase` against a live backend (`SHOWCASE_BE=…/v1` overrides the default, the local backend `server_ops.LOCAL_BE_URL`) |
| `extend_csvs.py` | CSV transforms: source area-fields, quartiles, author wiki-slugs, laureates; the bucket tables it reads are fetched once into `$EXTERNAL_DATA_ROOT/{metascience,wiki}/raw/`, and the laureates are the matched rows of `$EXTERNAL_DATA_ROOT/enrichment/laureates.csv` (OpenAlex id, name, category, year, Wikidata id, English Wikipedia URL, the evidence of the match and a note) |
| `sitemap_validation.py`, `survey_result_export.py` | Sitemap / survey export utilities |
| `calibrate_map.py` | Fits the world-map asset's Robinson projection (scale + offset per axis) against coastline landmarks — an extreme vertex of a country's mainland polygon vs its known coordinates — and checks coastal cities land on their country; bakes `src/lib/assets/data/map-projection.json`, read by `lib/utils/geo.ts` for the quiz's reveal map |
| `object_store.py` | Unified MCP object store: immutable per-run bundles (`<run>.jsonl.zst` under `paths.MCP_OBJECTS_REL`, written at `paths.ZSTD_LEVEL`) + payload-free version index (`mcp_objects` in the user DB, `paths.DB_REL`, keyed `(kind, obj_key, bundle)`, latest non-rejected wins); CLI `uv run -m pyscripts objects {list,ingest,export,set-status,fsck}` (`fsck` verifies every row's bundle address; exports compress to `.zst`); `gen_at` is stamped UTC ISO at write time; bundles ride the artifact-dir copy, index rows the user-DB handoff (see [mcp-server.md](mcp-server.md)) |
| `explore/` | Agent reasoning over the data: `paths/{bugs,features,stories}.py` review Playwright snapshots (`make explore`); `deep.py` (`uv run -m pyscripts.explore.deep`, `make deep-explore`) drives an agentic session with the `mcp_server/` tools against a chosen backend (foci: share/query/data-issue + endpoint suggestions; `--subject`/`--question`/`--investigate` scoping), re-issuing every cited number and writing story-only `report.md` + `reproduce.md` + `findings.json` (+ `runs.jsonl`) to its dir under the run root, `$EXTERNAL_DATA_ROOT/runs/`; with `--story ["<occasion>"]` the run ends with `story.py`: one article written from the fully reproduced findings only, as `story.md` (front matter with the title, date, occasion, run, the backend's data version, the first card as the preview image and every number no reproduced value accounts for) beside the card PNGs it shows in `<run>/cards/` (fetched through `RANKLESS_RENDER_URL` when the cards render elsewhere than the site); `runner.py` pluggable mining engines (`--runner`, claude-cli today), `cli.py` headless-Claude runner (optional MCP), `evidence.py` snapshot loading (verification of cited numbers is `mcp_server/verify.py`, shared with the live `verify_claims` tool), `runs.py` shared agent-run identity (`<workflow>-<scope>-<UTC stamp>` names) and home (the run root), `game_card_mining.py` (`uv run -m pyscripts rankless-game-card-mining`) the batch-prompted mixed round over every CampusQuest card kind — a deterministic harness (`unusable`, `menu`) decides which kinds each anchor can carry from the recognizable-institution roster (`src/lib/assets/data/recognizable-institutions.json`, `{semId: tier}`), the curated notes (`src/lib/assets/data/institution-notes.json`, `{semId: note}`), generic and shared display names and names stating their own place, and hands the model per-candidate menus (open kinds, nearest roster institutions with km) plus the roster as the only legal option pool; the model proposes question shapes only (kind, anchor, option ids or decoy names, reveal note), `judge` recomputes every answer from `get_entity_profile` facts re-issued through `mcp_server.verify` (stored on the card as `facts`) and drops what fails; the cards land as one object-store bundle, and the report in the run dir carries per-batch model spend and the held-back table (docs/mcp-server.md §Generator workflows) |
| `build_mcp_manifest.py` | Bakes `src/lib/assets/data/mcp-manifest.json` for the `/mcp` page from the live tool docstrings / resources / prompts (`make mcp-manifest`), filling the texts built from served values (the table tools' metric lists, the era's years) from `--backend` (default local) through the server's own `fetch` + `describe`; see [mcp-server.md](mcp-server.md) |
| `userdb.py` | The user-data unit (the user DB `paths.DB_REL` + the object store `paths.MCP_OBJECTS_REL`): consistent snapshots, cross-box table transfer with decision reconciliation, and retained off-box backups (`uv run -m pyscripts userdb {transfer,snapshot,backup}`); deploy.py provides the transport (see [deploy.md](deploy.md) → Backups, [mcp-server.md](mcp-server.md) → Moving the user data between boxes) |
| `services.py` | Unified service setup (`make setup-services ARGS="--profile dev"`): renders the `deploy/` systemd unit templates (`{{ var }}` placeholders) with real machine values (repo root, data root, MCP backend URL toggle, the MCP server's `mcp_server.MCP_HOST`/`MCP_PORT`) and installs them into `~/.config/systemd/user`; profiles dev / small-alpha / live / worker pick which of backend, frontend blue+green, mcp-server, status (`rankless-status.service` = `status_dump.sh` under systemd, the producer of the `/status` nginx serves on `STATUS_PORT`, defined here) run. `deploy.py` renders the same templates over SSH |
| `migration_scripts/` | One-time catch-up scripts for already-deployed state (`python3 -m pyscripts.migration_scripts.<name>`, stdlib-only so they run on a serving box's runtime venv). The app, the pipeline and the ops commands only ever speak the current schema and formats — never a version check, never a branch for an older shape; when a change strands a deployed database or data directory, the catch-up lands here, runs once per box and is deleted with the same commit that stops needing it. The directory is empty in steady state: a script lives one deploy cycle — every code deploy runs them all (`Transper.run_migrations`, `module_names()` enumerates the package) with the box venv before the build, the author runs it on the primary host's DB, the next commit deletes it, and ship/promote refuse while any remain. By hand use the box's own interpreter (`python3 -m …` or `uv run --frozen --no-default-groups python -m …`): a bare `uv run` re-resolves the default dependency groups and fails on the `libs/ccl-science-data` path source only build boxes have |

### Generated Python types (`wire/`)

The Python form of every `#[wire]` Rust type and constant (`make types`), TypedDicts and `Final` values in one module per Rust module, imported by `mcp_server` and `pyscripts` (`from wire.rankless_rs.user_ledger import WorkSubject`, `from wire.rankless_server.consts import PORT`); see [type-generation.md](type-generation.md). The constants, in these modules and in their TS twins under `src/lib/wire/`:

| Module | Constants |
| --- | --- |
| `rankless_server/consts` | `PORT`, `MAX_SLICE`, `MAX_METRIC_IDS`, `MAX_PINS`, `SCREEN_K`, `COMMIT_HASH_LEN` |
| `rankless_server/responses` | `METHODOLOGY`, `TREE_SPECS` |
| `rankless_rs/env_consts` | the env's pipeline thresholds: `MIN_PAPERS_FOR_INST`, `MIN_PAPERS_FOR_SOURCE`, `MIN_AUTHOR_WORK_COUNT`, `MIN_AUTHOR_CITE_COUNT` (committed with the `full` env's values) |
| `rankless_rs/metrics` | `PAPER_SCORE`, `TOP_N`, `MIN_TOPIC_SCORE`, `TOP_HIT_PAPERS`, `MAX_SHARED_PAPERS`, `SPEC_CORR_RATE` |
| `rankless_rs/ladder` | `LADDER_PCT_BANDS` |
| `rankless_rs/user_ledger` | the user-ledger file names: `ACTIVE_JSONL`, `CURATED_JSONL`, `SNAPSHOT_MANIFEST`, `OWNER_PINS`, `APPLIED_MANIFEST`, `DERIVED_MANIFEST`, `FORCED_WORKS` |
| `rankless_rs/derived_ledger` | `EXTERNAL_DATA_ROOT` (the env var), `DEFAULT_EXTERNAL_DATA_ROOT`, `NAMES_TABLE` |
| `rankless_trees/part_iterator` | `PARTS_ROOT_VAR` (the env var), `DEFAULT_PARTS_ROOT` |

### Gen reader audit (`pyscripts/typeaudit/`)

`__main__.py` (`make type-audit`) checks that the ccl-science-data regex reader still finds the dmove entities in `rankless_rs/src/gen/`; see [type-audit.md](type-audit.md).

### MCP server (`mcp_server/`)

Python MCP proxy (stdio `uv run -m mcp_server` / `make mcp-server`; streamable-http on
`MCP_HOST`:`MCP_PORT` behind nginx's `/mcp` location on the API host) exposing the Rust backend to any MCP client, with
receipts on every response and a `verify_claims` tool; see [mcp-server.md](mcp-server.md).

| File | Role |
| --- | --- |
| `server.py` | FastMCP wiring: at start `fetch` reads the backend's `/columns` (an unreachable backend fails the start) and `build` calls `describe(registry)` before registering the data tools in the receipt envelope, `PLAIN_TOOLS` (the grounding tools and `make_card`) as they are, `resources()`/prompts, server `instructions`; stdio or streamable-http (host and port default to `mcp_server.MCP_HOST`/`MCP_PORT`, the env vars of those names override them), `MCP_PUBLIC_HOSTS` host guard for the hosted endpoint |
| `tools.py` | Data tool implementations as plain async functions (`TOOL_FNS` registry, re-issued by `verify.py`); `describe()` fills the docstrings that state served values: the table tools' metric lists from the registry, and `ERA_DOCS`, the docstrings naming the recent era, with `yearlyCounts`; the limits they state are the generated constants (`SCREEN_K`, `MAX_PINS`, `TOP_HIT_PAPERS`, `MAX_SHARED_PAPERS`) |
| `receipts.py` | `{receipt, data}` envelope + per-session receipt log (keyed by MCP session id, bounded) mirrored as daily JSONL under `MCP_LOG_DIR`; `with_receipt` wraps a plain tool for registration |
| `grounding.py` | `verify_claims` (re-issue cited numbers by receipt id or tool+args, one fact-record format) and `suggest_endpoint` (log what the tools lacked) |
| `verify.py` | Deterministic re-issue of model-cited tool calls (`verify_facts`, dotted-path walk); shared by the live tool and every offline miner |
| `client.py` | Async httpx client for the backend (`RANKLESS_BE_URL`, default `BACKENDS["local"]`, the local backend on the generated `PORT`) |
| `response_shaping.py` | Tree flattening via the `TREE_SPECS` breakdowns, list truncation, `rankless_url` backlinks, `coauthor_edges` (upper-triangle `authorNetwork` → named strongest ties) |
| `__init__.py` | `MAIN_DOMAIN`, the one domain literal `BACKENDS`, `SITE_URL` and `pyscripts/hosts.py` derive from (the local backend on the generated `PORT`); `MCP_HOST`/`MCP_PORT`, where the server listens over HTTP (`services.py` renders the port into the unit and the nginx `/mcp` location); root/view types, the Nobel category list, and the site URLs a response links to: `entity_url` (a page, with its view state), `card_url` (a share card kind of an entity or a type's cohort, with its variant), `table_url`; `render_url` maps a card URL onto `RANKLESS_RENDER_URL` when the cards render elsewhere than the site |
| `cards.py` | `KINDS`, the card contract read from `src/lib/assets/data/card-kinds.json` (the file the site's loaders parse by), `profile_cards` (the kinds an entity's `/views` profile proves it has; a network needs the contract's `network.params.n.min` co-authors), `fetch_card` (a card's PNG from the rendering host, also `explore/story.py`'s fetch) and the `make_card` tool, which builds a variant's URL and fetches it once so a bad parameter fails in the session |
| `resources.py` | `resources()`: the schema/guide resources by URI (`rankless://schema/entity-types`, its recent era filled from `METHODOLOGY.yearlyCounts`; `rankless://guide/agent` = the resolve → call → cite → verify → answer loop) |
| `prompts.py` | Reusable prompts (`author_impact_report`) |

---

## Data flow

```
OpenAlex CSV dumps
  → rankless_rs steps (a1→a2→links1-5)
  → binary data files + generated Rust source (src/gen/)
      → rankless_trees (Getters, TreeRunManager)
          → rankless_server (Axum, on PORT)
              → SvelteKit SSR (+page.server.ts)
                  → Svelte components (SVG rendering)
```

Entity hero page request: SvelteKit calls `/v1/query` → server looks up entity by semantic
ID → `Getters` traverses tree → `TreeRunManager` builds `TreeResponse` (tree + papers +
related entities + yearly stats) → frontend renders `TreeSvg`, `ConceptMap`, `WorldMapSvg`.

**Entity types:** `authors`, `institutions`, `sources` (journals), `countries`,
`subfields`, `hit-papers`. Each entity has _production_ (own papers) and _impact_ (papers
citing those) sets.

**Metrics** are declared once beside the columns they read, in `rankless_trees/src/metrics.rs`, and served per root at `/v1/columns`: each root's metrics with their kind and texts, and the root's default ordering (`default_sort`: sources by Top-N mean, N their `TOP_N`; authors, institutions and countries by weighted total paper score; hit papers by paper score; subfields, which have no weighted total or Top-N mean, by citations), which a `/v1/slice` without `sort=` uses too. A metric is something that can be computed from a root's columns (the `dm_id`-indexed attributes `RootColumns` loads: papers, citations, era records, profiles, …): one declaration holds its label, meaning and rationale — templates over the methodology constants, filled per root by `MetricDecl::texts` (a Top-N mean's N, a recent h-index's year), so no text restates a number — its value type (count, score, share, year, or an entity reference such as an institution's country, single or set-valued), its parameter (a field, a country, a year window), and the columns it reads, whose `Coverage` (every indexed paper, the scored ones, those since a recent h-index year, or the years with yearly counts) `texts` appends to its meaning as a year span. Per root type its kind is derived, never typed: **global** where every column it reads is loaded and their scan fits `SCAN_BUDGET_BYTES` in one request, **intricate** where they are loaded but too large (an author's subfield row is one, a count per subfield for every author). A walk metric is a third case — it reads no column, so its availability is the tree specs' to settle: it is intricate where the root's trees open on its `Level` and absent where they never do, which is how `cited_from` exists for one root and not another. The table speaks one expression language, parsed only on the backend (`rankless_expr`, bound in `rankless_server/src/cohort.rs`): a metric is a call (`papers`, `field_score(oncology)`, `window_papers(2020, 2024)`, `cited_from(usa)`), `sort=` names one, and `where=` combines clauses `call op value` with `and`, `or`, `not` and parentheses (SQL precedence); numbers take `= != < <= > >=` and `in`, entity values `= != in not in` with a semantic id or a quoted name (`country = hun and city != "Budapest"`), and on a set-valued metric `=` means any equals and `!=` none does. `/v1/slice/:etype/:from/:to?sort=&where=` orders the narrowed cohort by a global metric (citations directly, every other parameter-free global metric from startup orderings, anything else a keyed scan); a sort or a clause on an intricate read-cost metric is screen-then-refine: the cohort's top `SCREEN_K` by citations after the global clauses, then the per-entity metric over those. A page answers `{rows, meta}` — uniformly, so a caller that only wants the ranking reads `rows` and ignores the rest: `meta.total` is the narrowed cohort's size, `meta.screened` the ranked set's size when the ranking is screened and `null` otherwise (a screened `rank` is within the ranked set, not within the cohort), and `meta.columns` lists the metric columns the rows carry in display order (every parameter-free global, the sort's parameter family, every parameterized clause), each row's `values` keyed by those same calls. `pin=` returns the named entities' rows in the active ordering, rank-less outside the ranked cohort. `/v1/metrics/:etype?ids=&metrics=` answers a list of calls for a page of ids, keyed by call, a walk metric read from each entity's first-level profile in the tree cache — capped at `MAX_METRIC_CALLS` calls over `MAX_METRIC_IDS` ids, because a walk costs one tree query per pair; `/v1/where?q=` returns an expression's tree for a client that shows it as chips. Adding a metric is one declaration plus one arm of the reader; adding a column to `RootColumns` makes every metric over it exist wherever the column loads.

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
  different `treeId`; `loadNewQc` fetches that tree through the component's `tree-loader`, which drops a response a newer request has superseded.
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

The `gen-release` profile (inheriting `release`'s full optimization, LTO and single codegen unit; `Cargo.toml`) makes each compile
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
| --- | --- | --- |
| `rankless_rs/steps/a2_init_atts.rs` | `Worker<T>::para()` | CSV rows: works, biblios, authorship |
| `rankless_rs/steps/a1_entity_mapping.rs` | `std::thread::spawn` + `Vec<JoinHandle>` | Independent entity ID mapping |
| `rankless_rs/steps/derive_links2.rs` | `par_join!` | 5 `CiteDeriver` methods |
| `rankless_rs/steps/derive_links3.rs` | `para_multi_gen_run!` + `Worker<T>::para()` | Work counts per entity; peer selection |
| `rankless_rs/src/common.rs` | `make_interface_struct!` | Parallel data loading at server startup |
| `rankless_trees/src/io.rs` | Persistent pool (`VecDeque` + `Condvar`) | Tree query serving; the server's thread count |
| `rankless_server/src/main.rs` | `para_multi_gen_run!` + Tokio (as many workers as the tree pool's threads: `RANKLESS_THREAD_COUNT`, else `DEFAULT_N_THREADS`) | Entity state init; HTTP handling |

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

This: (1) clones `ccl-science-data` into `CCL_CLONE_DIR` (`DEFAULT_CCL_CLONE_DIR` in `pyscripts/dev/bootstrap.py` when unset) and regenerates its reader bindings; (2) `uv sync` + `bun install`; (3) downloads the nano snapshot from `NANO_ARTIFACT_URL` into `OA_SNAPSHOT`; (4) runs the pipeline (`RANKLESS_ENV=nano`) → `OA_ROOT` (~10 min first time); (5) builds `rankless-server` (`RANKLESS_ENV=nano` so compile-time constants match the data). Idempotent — stamp files (`SNAPSHOT_STAMP` in `OA_SNAPSHOT`, `PIPELINE_STAMP` in `OA_ROOT`) skip finished steps.

**Daily flow:**

```sh
make dev            # backend on PORT + SvelteKit on devPort (dev.json), interleaved logs
uv run -m pyscripts.dev.run --open   # auto-launch browser
```

**Testing & coverage:**

| Command | What runs |
| --- | --- |
| `bun run test` | Playwright e2e (`tests/`, builds + previews on `previewPort` from `dev.json`, against a scratch user DB + object store: `E2E_ENV` in `tests/e2e-env.ts`, named after `paths.json`, so seeded fixtures never land in `data/`). `ledger.spec.ts` is excluded via `testIgnore` |
| `make mega_test` | The ledger integration test (`ledger.spec.ts`) — orchestrates dev server + backend + a pipeline run between its `pre-pipeline`/`post-pipeline` phases via `playwright.ledger.config.ts` |
| `make test-ledger` | The Rust ledger gate (`rankless_rs/tests/ledger_pipeline.rs`): a synthetic snapshot through `to-csv → derive-ledger → filter → a1_entity_mapping`, in-process, in seconds; also part of `cargo test`. `make fixture-build` writes that snapshot, the ORCID registered-name table + `scenario.json` to `FIXTURE_DIR` (default `/tmp/rankless-fixture`) for driving the flow by hand |
| `bun run test:unit` | Vitest unit tests (`src/**/*.test.ts`) — the TS logic in `src/lib` |
| `bun run test:unit:cov` | Vitest with V8 coverage of `src/lib/**/*.ts` → `coverage/index.html` |
| `bun run test:e2e:cov` | Playwright (same specs as `bun run test`) with browser coverage → `coverage-e2e/index.html` |
| `make coverage` | Runs `test:unit:cov` + `test:e2e:cov` (failures tolerated — the reports still generate), then opens both reports in Firefox |

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

**Where things live:** `OA_SNAPSHOT` (downloaded JSON, gitignored), `OA_ROOT` (local pipeline output, gitignored), `libs/ccl-science-data` (symlink → the `CCL_CLONE_DIR` clone), `target/release/rankless-server`, `.env` (gitignored, seeded from `.env.example`, whose `PUBLIC_BACKEND_URL` and `PUBLIC_ORIGIN` ports `pyscripts/tests/test_dev_setup.py` checks against `PORT` and `devPort`, since a dotenv file cannot derive them). External data the pipeline reads but does not produce (the ORCID registered-name table, the laureate table, the bucket tables `extend_csvs` joins) lives under `EXTERNAL_DATA_ROOT`, a directory per source outside the repo and both trees; unset it is `DEFAULT_EXTERNAL_DATA_ROOT`, where the bucket tables land and, without the ORCID table, `derive-ledger` picks each ORCID's owner by works alone and `extend_csvs` writes no laureates.

**Troubleshooting:**

| Symptom | Fix |
| --- | --- |
| `Server already running at …`, or the dev server's port taken | `lsof -nP -iTCP:<port> -sTCP:LISTEN` on the port it names (`PORT`, or `devPort` in `dev.json`) finds the other instance |
| `backend never became ready` | inspect `make dev` output; usually incomplete OA_ROOT — re-run `make bootstrap` |
| `NANO_ARTIFACT_URL` 404 | the artifact host isn't reachable; get a fresh URL |
| ccl-science-data import error | `rm -rf libs/ccl-science-data && make bootstrap` |

**Maintainer — refreshing / testing the snapshot artifact:** the artifact is just the
filtered raw JSON snapshot in OpenAlex's `data/jsonl/<entity>/` layout (no pipeline output, no binaries). Prereq:
`$OA_TEST_ROOT/nano-snapshot/` (build once with `uv run -m pyscripts.make_test_dataset`).

```sh
uv run -m pyscripts.dev.build_nano_artifact     # tars + zstds the snapshot, prints SHA-256 + URL lines
python -m http.server 8000                      # serve it
make test-dev-env                               # full bootstrap in a clean Ubuntu container, verifies serve
NANO_ARTIFACT_URL=http://10.0.0.5:9000/nano-root.tar.zst make test-dev-env   # override host
```

`make test-dev-env` uses `--network=host` (Linux); macOS hosts would swap the URL for
`host.docker.internal:8000`.
