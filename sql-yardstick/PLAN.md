# Reproduction Plan

## Current state

`flask.py` + `views.sql` is the working baseline. It handles `institutions`, `authors`, and `countries` as root types, and `authors`, `institutions`, `countries`, `sources`, `subfields`, `works` as node types.

**Known bug**: counts are summed rather than unioned — see "Counting semantics" section of `repro-prompt.md`.


---

## ~~Phase 1 — Fix the union/deduplication bug~~ DONE

`build_tree_query` + `rows_to_tree` replaced with `build_level_query` + `build_tree` in `server.py`. One query per depth level, each grouping by the key prefix up to that depth and using `COUNT(DISTINCT source_work)` / `COUNT(DISTINCT (source_work, citing_work))`. Parent node counts come from their own query, not by summing children.

**Test**: verify that summing all leaf-level `sourceCount`s exceeds the root `sourceCount` (expected, multi-attribution is fine) but that each individual node's count matches a direct query on that filter.


---

## Phase 2 — Complete root type support

Missing root types and their lookup paths:
- `sources` — works via `works-locations.source`
- `subfields` — works via `works-topics` → `topics.subfield`

`ROOT_COLUMN_MAP` in `flask.py` must be extended. The `root_works` CTE in `build_tree_query` currently assumes everything goes through `work_authors`; it needs a per-root-type sub-query strategy.

Clean approach: add a `ROOT_MAP` dict parallel to `NODE_MAP` that specifies the view and column for each root type, and build the `root_works` CTE dynamically from it.


---

## Phase 3 — Complete node type support

- `topics` node type: join `work_subfields` then resolve topic from `works-topics`; or add a `work_topics` materialized view similar to `work_subfields`.
- `works` node type: already partially mapped in `NODE_MAP` (column `work_id`, no table join needed since impact edges already carry `source_work`/`citing_work`). Wire it up properly.
- `fields` and `domains`: not in the API spec but may be useful for debugging/testing; defer.


---

## Phase 4 — Views and indexes

Current `views.sql` creates materialized views. Review after phases 1–3 to confirm:
- Indexes cover all join columns used by `build_tree_query`
- `work_subfields` deduplicates correctly (a work with 3 topics in the same subfield should appear once per subfield, not 3 times)
- `work_authors` deduplication: a work with 2 authors at the same institution appears once per institution per work, which is correct for sourceCount but must be handled in counting

Consider adding a `work_fields` and `work_domains` view for Phase 3.


---

## Phase 5 — Systematic validation

Extend `comp-eval.py` to:
1. Run a matrix of `(root_type, root_id, breakdown)` combinations against both `flask.py` and the real backend
2. Compare `linkCount` and `sourceCount` at each tree node (not just the root)
3. Report relative error per node and flag nodes exceeding a threshold (e.g. >1% discrepancy)
4. Track which breakdown configurations expose the largest errors

This becomes the regression harness: every fix in phases 1–3 should reduce the error matrix.


---

## Phase 6 — Edge cases and data quality

- Works with zero topics: excluded from subfield/topic breakdowns — verify they don't silently vanish from sourceCount
- Works with no citations: sourceCount = 1 but linkCount = 0 — verify tree handles this
- Null institutions in authorships: `works-authorships.institution` can be null; `work_authors` must handle this (currently does via LEFT JOIN but country_code will be null too)
- Very large entities (institutions with 100k+ works): profile query time, consider per-request temp tables or smarter caching
- Root entity with no works: should return empty children, not an error


---

## Milestones

| Phase | Done when |
|-------|-----------|
| 1 | Node counts match direct SQL queries; no over-counting for multi-attributed works |
| 2 | All 5 root types return correct results |
| 3 | All node types work in breakdowns |
| 4 | p99 latency < 2s for a 3-level breakdown on a mid-sized institution |
| 5 | Validation harness runs and error < 1% across test matrix |
| 6 | No crash or wrong count on known edge-case inputs |
