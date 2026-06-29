# Rankless v2 → v3 — Executive Summary

What changed between the **v2** release (commit `34cd6b8c`, 2026-03-05) and **v3** (current
`rankless-main`). Scope: 656 commits, ~376 files. This is a curated summary of the changes
that matter; per-file detail lives in git and [`architecture.md`](architecture.md).

The test for "new" here is **what users can actually reach on the live site** — features whose
code predates v3 but weren't reachable on the live v2 site count as new. Tags: **NEW** = newly
available to users · **ENHANCED** = already live in v2, substantially reworked.

---

## Headline: from a viewer to a participatory platform

v2 was a read-only impact explorer. v3 turns each entity page into a richer, comparative
profile and — for the first time — lets researchers **correct their own record**.

## 1. ORCID login + public user ledger — NEW

Researchers sign in with their ORCID iD and curate their own profile: **claim** papers,
**disown** wrongly-attributed ones, **merge duplicate papers**, and **merge duplicate author
profiles**. Every action is appended to an immutable, publicly auditable ledger (hashed per
subject so submissions can be verified); pending actions can be edited or cancelled, and
applied ones revoked on the next data refresh. Disowns and paper-merges apply automatically;
claims and author-merges are queued for moderation.

## 2. Peers comparison — NEW

Every institution, country, journal, and author is now placed against ~5 algorithmically
similar peers. Mini per-subfield citation bars summarise each peer; selecting one opens
**citations-by-field and citations-by-year** charts expressed as multipliers against that
peer. Subfield chips carry percentile **"standing" badges** (top 5% … top 0.01%), derived
from a per-field citation "ladder". Any peer can be swapped for an arbitrary entity via search.

## 3. Redesigned entity pages — NEW

A type-aware hero header replaces the old layout: each entity kind (author, institution,
journal, country, field, hit-paper) gets its own headline stat, "impact in / papers in" field
tiles with nested topics, standing badges where meaningful, and contextual leader rows
(e.g. an author's co-authors / journals / partner nations). Everything below now lives on this
one unified page; the old `author-papers` sub-page (unreachable on the live site) was removed.

## 4. Co-authors: network, timeline, and shared papers — mixed

- **Co-author network** (ENHANCED): force-directed graph of an author's most-cited collaborators.
- **Co-author timeline** (NEW): every collaborator placed by the years they published together,
  with threshold/sort controls — surfacing recent or minor collaborators the network omits.
- **Shared papers** (NEW): clicking a node shows papers co-authored with that person; clicking an
  edge shows papers the pair shares; if none overlap with the author, their own two-way
  intersection can be loaded on demand.

## 5. All Works list + citation export — NEW

Every author profile now carries their full body of work as a first-class section: a paginated,
server-seeded, sortable table with export in **HTML / Chicago / APA / MLA / BibTeX (+ `.bib`)**,
min-cite / since-year / top-N filters, and an owner paper-merge/dedup workflow. (On the live v2
site this list was unreachable — see notes.)

## 6. Hit papers & standout-paper breakdowns — NEW

An author's standout ("hit") papers are surfaced directly on their profile as a colour-coded
"rainbow", each linking to a **breakdown** — a treemap of which research domains cite the
paper — with a plain-English explainer of why it qualified. The qualifying threshold was lowered
(≥5000 → ≥500 citations, plus benchmark- and topic-based criteria), surfacing many more papers.

## 7. Search & discovery

- **Dedicated `/search` page** (NEW): unified results across all entity types with keyboard
  navigation.
- **Browser OpenSearch** (NEW): add Rankless to the browser's address-bar search.
- The custom search engine (`muwo_search`) gained binary serialization for faster startup.

## 8. Topic origination & leadership — partially shipped

Papers that **originated a topic** are flagged ("★ originated …") in the standout-papers view,
backed by new topic-creator/dominator computation in the pipeline. The broader
"topic leadership" listing component is still **work-in-progress (uncommitted)** and not yet live.

## 9. Platform, performance & infrastructure — NEW

- **Server refactor**: the monolithic `main.rs` (~1250 lines) split into focused
  `handlers/` + `state` / `startup` / `responses` / `search_cache` / `util` modules.
- **Memory-mapping**: large fixed-size attribute arrays (per-subfield citations, top-N
  relation tables) are mmap'd instead of held on the heap; shared labels use `Arc<str>` —
  substantially lower RAM.
- **Pipeline parallelism + zstd**: parallel CSV filter/write and link derivation under a
  memory budget; pipeline CSVs compressed.
- **Perf-comparison framework**: compares two git refs in Docker, capturing phase timings and
  peak memory with a correctness diff (`docs/benchmarking.md`).
- **Monitoring & reporting**: nginx-log parsing, bot/human session classification, and HTML
  dashboards; live resource alerts.
- **SEO**: per-entity sitemap shards + OpenSearch descriptor.
- **Toolchain**: migrated to **Svelte 5** (runes) and **Bun**; added Playwright e2e/coverage
  infra and a Docker dev-test image.

---

## Notes & caveats

- On the live v2 site, an author's **full works list, citation export, and standout-paper
  breakdowns** were not reachable (gated behind an unlinked sub-page), so they are counted as new
  above even though some of their code predates v3.
- **Claims/author-merges** are recorded and moderated; end-to-end application of claims may be
  partial — verify before promising it in user-facing copy.
- The **co-author timeline** landed late in the cycle and may still be settling.
- Several features are **built but not shipping** in this version (Path to Person, Browse tables,
  the topic-leadership listing) — tracked in [`unfinished-features.md`](unfinished-features.md).
