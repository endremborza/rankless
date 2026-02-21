# Rankless

Rankless is a large-scale scholarly data exploration platform that enables low-latency, interactive browsing of a large citation network. It is built around data-specific compilation and selective caching to make real-time exploration of millions of citation relationships feasible.

## Data Schema

The dataset is sourced primarily from OpenAlex, extended with SCImago rankings and categorizations. It is organized around six primary entity types: Papers, Authors, Institutions, Sources (journals), Countries, and Disciplines. The Disciplines type is further resolved into a four-level hierarchy: Domains (4), Fields (26), Subfields (252), and Topics (4516), where the first three correspond to ASJC codes.

The critical relationships in the graph are citations, authorships, and topical classifications of papers. Affiliations are a special case: they link one or more institutions to an authorship, which is itself already a link between an author and a paper.

Each searchable entity — Authors, Institutions, Sources, Countries, and Subfields — has a hero page built around two sets of papers: its *production* (papers associated with the entity) and its *impact* (papers that cite those).

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
    TEXT abbreviated_title
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
  "fields"               ||--|{ "domains"               : "domain"
  "subfields"            ||--|{ "fields"                : "field"
  "topics"               ||--|{ "subfields"             : "subfield"
  "topics"               ||--|{ "fields"                : "field"
  "topics"               ||--|{ "domains"               : "domain"
  "works-authorships"    ||--|{ "works"                 : "parent_id"
  "works-authorships"    ||--|{ "authors"               : "author"
  "works-authorships"    ||--|{ "institutions"          : "institution"
  "works-locations"      ||--|{ "works"                 : "parent_id"
  "works-locations"      ||--|{ "sources"               : "source"
  "works-referenced_works" ||--|{ "works"               : "parent_id / referenced_work_id"
  "works-topics"         ||--|{ "works"                 : "parent_id"
```

## Visualizations

### Hierarchical Tree

An interactive breakdown of an entity's production or impact across topical, geographical, and institutional dimensions. Users navigate levels of the hierarchy from broad domains down to specific subfields, and can configure what each level of the tree represents using dropdown selectors. Each branch also surfaces the most cited paper within that category.

### Research Space

A network where nodes represent research fields and edges connect fields that tend to share authors. Colored nodes indicate fields where the entity's papers appear. Because papers can be assigned to multiple fields, a single paper may appear in several nodes. This view helps anticipate where an entity is likely to publish next and lets users find the most-cited paper within any given field.

### Collaborator Network

A co-authorship network scoped to an author's most frequent collaborators. It reveals clusters of collaboration and the structure of research partnerships.

### Geographical Impact Map

A map of citation flows by country: how many citations the entity's papers receive from authors working in each country. Can be colored by *specialization*, comparing observed citations against an expected baseline derived from each country's overall research output.

## System Architecture

### Data Processing and Preparation

Raw data is ingested from OpenAlex and Scopus dumps and transformed by a suite of custom Rust applications (`rankless_rs`, `dmove`). A core technique is metaprogramming via the `dmove_macro` and `dmove` crates: rather than writing generic data-handling logic, the build process generates Rust source code tailored to the specific shape of the dataset. This data-specific compilation produces optimized data structures and query paths that are a direct function of the dataset's characteristics. The output is a set of binary data files and generated Rust source, consumed directly by the backend server.

### Backend

The server is written in Rust (`rankless_server`) and handles all API requests against the pre-processed data.

Search is handled by `muwo_search`, a custom engine built around the proprietary data structures for fast partial-string queries.

Caching is proactive: `pyscripts/cache_prompting.py` identifies entities whose on-demand computation would be too memory-intensive using the standard path, and pre-warms the server's in-memory cache before the first user arrives. For a small number of high-traffic entities this also involves a special calculation method that avoids the otherwise-prohibitive memory footprint.

### Testing

Testing is structured in three layers, each serving a distinct purpose.

**Unit tests** (Rust, in `dmove/tests` and `rankless_rs/tests`) validate the correctness of individual data processing routines and backend logic in isolation.

**End-to-end tests** (Playwright, in `tests/test.ts`) simulate real user interactions across the full stack. Because much of the application's text — chart annotations, statistical summaries, entity descriptions — is generated dynamically at render time from live data, it cannot be proofread statically. The e2e suite therefore exports all rendered paragraph text to `paragraph_texts.txt` after each run, making it straightforward to spellcheck the complete set of dynamically-generated prose as a post-processing step.

**Integration and performance tests** (`pyscripts/bm.py`) benchmark the system and verify that the pieces interact correctly under load.

All three layers are run against three different sizes of data subsets: a small subset for fast CI validation, a medium subset for thorough functional correctness checks, and a large subset for realistic performance and scalability testing.

Deployment itself is also tested end-to-end using QEMU/KVM, ensuring the full deployment pipeline works correctly before hitting production.

### Frontend

The frontend is a Svelte/SvelteKit application. All visualizations — trees, networks, maps — are rendered as SVG built from scratch, with the only external dependency being Cytoscape for network layout calculation. Interactive state management is handled through Svelte's reactive primitives, with complex logic extracted into utility modules (`src/lib/visual-util.ts`, `src/lib/tree-functions.ts`, `src/lib/tree-events.ts`).

### Deployment

Deployment is automated via `pyscripts/deploy.py`. The application runs on Linux, with systemd managing both the Rust backend and the Bun/Node frontend server. Nginx fronts the stack as a reverse proxy and serves static assets.

### Monitoring and Alerting

Live monitoring is handled by `pyscripts/live_monitoring.py`. To eliminate false positives from transient network issues, a distributed swarm of monitoring nodes is used: an alert is only raised when multiple independent monitors agree that something is wrong. Nginx logs are parsed hourly to produce performance reports on traffic and response times. When a genuine issue is detected, the alerting system sends an email to the team.
