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

## Architecture

**Processing (`rankless_rs`):** Ingests OpenAlex/Scopus CSV dumps through a six-step pipeline (entity mapping → attribute init → link derivation). Uses `dmove`/`dmove_macro` metaprogramming to generate Rust source tailored to the dataset, producing optimized binary data files.

**Backend (`rankless_server`):** Axum HTTP server (port 3038) over pre-processed binary data. Custom partial-string search (`muwo_search`). Proactive cache pre-warming (`pyscripts/cache_prompting.py`) for high-traffic entities. KD-tree for institution geo queries.

**Tree library (`rankless_trees`):** Hierarchical query engine with thread pool (`TreeRunManager`), citation path finder (`path_finder.rs`), and in-memory caching.

**Frontend (`src/`):** SvelteKit/Svelte with SSR. All visualizations hand-written SVG; Cytoscape.js the only external viz dependency. ORCID authentication for user profiles. Dark mode responsive, color scheme defined in `src/routes/styles.css`

**Deployment (`pyscripts/deploy.py`):** Linux, systemd (Rust backend + Bun frontend), Nginx reverse proxy, Let's Encrypt SSL. Live monitoring via distributed alert swarm (`live_monitoring.py`). Nginx logs parsed hourly for performance reports.

**Testing:** Unit tests (Rust), E2E via Playwright (exports rendered prose for spell-checking), integration/performance benchmarks (`pyscripts/bm.py`). Three data subset sizes: small (CI), medium (correctness), large (scale). Deployment pipeline tested with QEMU/KVM.
