# Rankless — Overview

**Rankless** is an interactive scholarly data explorer for real-time browsing of large citation networks. It enables low-latency exploration of millions of citation relationships across papers, authors, institutions, journals, countries, and research disciplines.

## Data

Source: OpenAlex (primary) + SCImago/Scopus (journal rankings).

Six entity types: **Papers, Authors, Institutions, Sources** (journals), **Countries, Disciplines**.

Discipline hierarchy: Domains (4) → Fields (26) → Subfields (252) → Topics (4516), ASJC-based.

Core relationships: citations, authorships, topical classifications. Affiliations link institutions to authorships (author↔paper pairs).

Each searchable entity has a hero page built around **production** (its papers) and **impact** (papers citing those).

## Visualizations

- **Hierarchical Tree** — interactive breakdown of production/impact across topical, geographic, and institutional dimensions; configurable breakdown per level; surfaces most-cited paper per branch.
- **Research Space** — field-to-field network based on author co-occurrence; reveals likely future publication venues.
- **Collaborator Network** — co-authorship graph scoped to an author's frequent collaborators.
- **Geographical Impact Map** — citation flows by country; optionally colored by specialization vs. baseline.
- **Author Peers** — comparison table of an author against their 5 closest peers (by coordinate proximity + subfield similarity); subfield citation heatmap with color-scaled opacity, sparkline decade timeline, total papers/citations.
- **Hit Paper Breakdown** — lazy-loaded citation breakdown panel for individual standout papers: TileTreeMap of citing entities (shown inline when a paper is expanded in PaperRainbow or via the dedicated `/hit-papers/{semId}` profile page).

## Architecture

**Processing (`rankless_rs`):** Ingests OpenAlex/Scopus CSV dumps through a six-step pipeline (entity mapping → attribute init → link derivation). Uses `dmove`/`dmove_macro` metaprogramming to generate Rust source tailored to the dataset, producing optimized binary data files. See `docs/metaprogramming-make.md` for the build orchestration details.

**Backend (`rankless_server`):** Axum HTTP server (port 3038) over pre-processed binary data. Custom partial-string search (`muwo_search`). Proactive cache pre-warming (`pyscripts/cache_prompting.py`) for high-traffic entities. KD-tree for institution geo queries. Author peers endpoint (`/author-peers/:semid`) pre-loads peer ID array (Box) and memory-maps per-subfield citation counts at startup (OS-paged, ~4 GB resident savings).

**Tree library (`rankless_trees`):** Hierarchical query engine with thread pool (`TreeRunManager`), citation path finder (`path_finder.rs`), and in-memory caching.

**Frontend (`src/`):** SvelteKit/Svelte with SSR. All visualizations hand-written SVG; Cytoscape.js the only external viz dependency. ORCID authentication integrated into author profile pages (login redirects back to same page). SQLite (better-sqlite3, WAL mode) stores paper disown/claim actions per ORCID user. The main entity profile page (`/[rootType]/[...semanticId]`) handles all entity types: for authors it SSR-loads paper-profile, author-peers, and an initial 20-paper works batch in parallel with the tree, then renders FullQc (impact tree, dominant), PaperRainbow (standout papers, with inline HitPaperBreakdown panel per paper), AuthorPeers, geography/research-space/co-author-network sections, and a paginated AllWorks list (hit papers show a "breakdown →" link to their profile page). Owner paper-management actions (disown/merge/claim) unlock after the first "Load more" click. Hit-paper profiles (`/hit-papers/{semId}`) use DOI as semantic ID with `W{oa_id}` fallback for papers without DOIs; they show a publication year, external DOI/OpenAlex link, and the standard FullQc citation tree. A sticky TOC links all sections. The separate `/author-papers/:semId` page retains the citation impact DAG (ImpactDag) and is not prominently linked in v1 public profiles. Dark mode responsive, color scheme defined in `src/routes/styles.css`

**Deployment (`pyscripts/deploy.py`):** Linux, systemd (Rust backend + Bun frontend), Nginx reverse proxy, Let's Encrypt SSL. Live monitoring via distributed alert swarm (`live_monitoring.py`). Nginx logs parsed hourly for performance reports.

**Testing:** Unit tests (Rust), E2E via Playwright (exports rendered prose for spell-checking), integration/performance benchmarks (`pyscripts/bm.py`). Three data subset sizes: small (CI), medium (correctness), large (scale). Deployment pipeline tested with QEMU/KVM.
