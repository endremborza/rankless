# Reproduction Progress

## Baseline (before this session)

Comp-eval with root=Columbia (OA 78577930), 5 breakdown configurations:
- 1 root-matched case (tid=2: authorsS×countriesC×institutionsC), 4 root-mismatched

### Root-matched (same data, 1220 links / 278 sources)
- Node match rate: **4.3%** (243 matched, 5293 flask-only, 281 rs-only)
- linkCount: med_err=65.1%, corr=0.657
- sourceCount: med_err=12.5%, corr=0.750

### All (5 comparisons)
- Node match rate: 8.8%
- linkCount: med_err=90.9%, corr=0.681
- sourceCount: med_err=85.0%, corr=0.712

---

## Changes made

### 1. NULL filtering (INNER JOIN + WHERE IS NOT NULL)
- Switched `LEFT JOIN` → `JOIN` for breakdown tables
- Added `WHERE col IS NOT NULL` for each breakdown column
- Removed `COALESCE` with sentinel values and `null_default` from NODE_MAP
- **Impact**: Minimal (~2% reduction in flask-only nodes). Most NULLs were already rare.

### 2. DM ID mapping in SQL
- Added OA→DM mapping tables (`dm_authors`, `dm_institutions`, `dm_countries`, etc.) loaded from binary files at startup
- Flask queries now JOIN through mapping tables, outputting DM IDs directly
- Comp-eval simplified: removed `oa_id_map`, `cc_to_id`, `load_map` — no longer needs OA→DM translation for flask keys
- **Impact**: No accuracy change (mapping was already 1:1 bijection applied correctly in comp-eval). Cleaner architecture — flask speaks DM IDs natively.

### 3. Source-side root entity filtering
- When a source-side breakdown groups by a column from the root table (e.g., authors breakdown for institution root, both using `work_authors`), a WHERE clause restricts to rows where `root_column = :root_id`
- Only applied for "child entity" breakdowns (e.g., authors of institution), NOT for peer attributes (country_code, institution) to avoid over-restricting
- **Impact**: Major improvement for root-matched case

---

## Current state (after all changes)

### Root-matched (tid=2: authorsS×countriesC×institutionsC)
| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Node match rate | 4.3% | **12.3%** | +8pp |
| Flask-only nodes | 5293 | **1421** | -73% |
| linkCount med_err | 65.1% | **53.1%** | -12pp |
| linkCount corr | 0.657 | **0.765** | +0.108 |
| sourceCount med_err | 12.5% | **0.0%** | -12.5pp |
| sourceCount corr | 0.750 | **0.832** | +0.082 |

### All 5 comparisons
| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Node match rate | 8.8% | **9.6%** | +0.8pp |
| linkCount med_err | 90.9% | **90.9%** | -- |
| linkCount corr | 0.681 | **0.685** | +0.004 |
| sourceCount med_err | 85.0% | **84.6%** | -0.4pp |
| sourceCount corr | 0.712 | **0.714** | +0.002 |

### Per-comparison detail

| tid | breakdowns | root match | matched | flask-only | rs-only | lc corr | sc corr |
|-----|-----------|------------|---------|------------|---------|---------|---------|
| 2 | authorsS×countriesC×institutionsC | yes (1220/1220) | 240 | 1421 | 284 | 0.765 | 0.832 |
| 0 | subfieldsS×subfieldsC×topicsC | no (1220/5894) | 1119 | 9121 | 1299 | 0.602 | 0.788 |
| 1 | subfieldsC×sourcesC×topicsC | no (1220/5896) | 2042 | 16074 | 2955 | 0.547 | 0.704 |
| 6 | countriesS×subfieldsS×institutionsS | no (1220/5895) | 422 | 828 | 1956 | 0.861 | 0.947 |
| 3 | sourcesC×countriesC×subfieldsC | no (1220/5896) | 703 | 6937 | 1880 | 0.088 | 0.336 |

---

## Remaining discrepancies & next steps

### 1. Flask-only nodes (1421 in root-matched)
**Root cause**: Flask includes 145 authors (via OA authorship data), RS only 28 (DM-curated set). All 28 RS authors exist in flask output (zero RS-only at level 0). The 117 extra flask authors have valid Columbia authorships in OA but aren't in the DM's curated association.
**Fix**: Would need DM's author-institution association data.

### 2. Root-mismatched cases (4/5 configurations)
**Root cause**: PG micro-root test set has 278 source papers / 1220 edges. RS full dataset has ~1026 sources / ~5895 edges for most tids.
**Fix**: Load more data into PG, or identify which RS tids use the test subset.

### 3. Counting differences on matched nodes (linkCount med_err=53.1%)
**Root cause confirmed**: RS institution hierarchy rolls up sub-institutions under parents. E.g., for author 49034, country 1 (US) shows RS lc=139 (=ALL edges) vs flask lc=36. RS institution 3 (likely a top-level entity) also shows lc=139 while flask shows lc=10. This inflation pattern is consistent across all matched nodes.
**Evidence**: Side-by-side comparison of author 49034's citing-side institutions shows 17 distinct institutions between the two backends with only 3 overlapping — RS has hierarchical parent institutions, flask has flat OA institutions.
**Fix**: Would need institution hierarchy data to implement roll-up in flask.

### 4. sourceCount already excellent for matched nodes
After the source-side root filtering fix, sourceCount median error dropped to **0.0%** for the root-matched case. The author-level source counts match perfectly between flask and RS (verified for all 28 RS authors: 25/28 have identical sourceCount, 3 have small differences due to multi-institution authorships).
