# EntityPeers Component Redesign

## Goal

The current `EntityPeers.svelte` shows a table with subfield citation cells and per-row sparklines. The sparklines are too narrow to convey meaningful trend information. This plan describes data additions and five distinct component variants (A–E) to be implemented and displayed simultaneously for selection.

---

## Phase 1: Data Feed Expansion

### New fields in `PeerEntry` (Rust + TypeScript)

```ts
type PeerEntry = {
  // existing
  name: string;
  semanticId: string;
  papers: number;
  citations: number;
  subfieldCitations: number[];
  yearlyPapers: number[];   // ERA_SIZE = 11 years
  yearlyCites: number[];    // ERA_SIZE = 11 years
  startYear: number;
  // NEW
  hIndex: number;           // h-index for this author
  careerCentroid: number;   // normalized [0,1], 0=early career, 1=late career
  country: string | null;   // primary affiliated country name (null if unknown)
};
```

#### `hIndex` — requires pipeline re-run
- Compute per-author h-index in `derive_links2` (same approach as `get_h_index_and_sort` used for sources).
- Store as a fixed attribute under a new `AuthorHIndexMarker`.
- Load via `MmapBox` or `QuickestBox` in server; expose in `build_peer_entry`.

#### `careerCentroid` — requires pipeline re-run
- Already computed transiently in `derive_links3/peer_ctx.rs` (`compute_career_centroid`).
- Store as a fixed attribute under a new `AuthorCareerCentroidMarker` (f32, normalized).
- Load in server alongside `cit_subfields` in `AuthorPeerData`; expose in `build_peer_entry`.

#### `country` — server-only change, no pipeline re-run
- Already available per author in `prep_exts.prime_relations` (rel_type = 3, etype = Countries).
- In `build_peer_entry`, read from `astates.prep_exts[rid].prime_relations`, take first entry with rel_type == 3, resolve name via `satts`.
- Pass `satts` into `build_peer_entry`.

### Updated `EntityPeersResp` (no structural change needed)
The `topSubfields` and `hero`/`peers` split stays the same.

---

## Phase 2: Five Component Variants

All five variants receive the same `EntityPeersResp` (with expanded `PeerEntry`) and are rendered on a single comparison page. They share the same Svelte prop interface but differ in visual design.

The year range covered by `yearlyCites`/`yearlyPapers` is ERA_SIZE=11 years, from `MIN_YEAR` to `FINAL_YEAR`. The `startYear` field indicates when the author started publishing (may be before the ERA window).

---

### Variant A — Enhanced Table

Layout: same table structure as current, but with meaningfully improved columns.

**Columns:**
- Name + country flag/tag
- h-index (new column, right-aligned)
- Career stage indicator: a small dot on a horizontal bar representing `careerCentroid` (0=left=early, 1=right=late), shown instead of or beside `startYear`
- Subfield citation cells (same as current, with opacity encoding)
- Sparkline cell (wider, taller — min 160px, height 80px): citation trend only (no dual channel), with hero reference dashed line; scale is shared across all peers (global max)
- Papers | Citations stats

**Visual notes:**
- Career stage bar: a thin 40px track with a filled circle at the centroid position; hero's centroid shown as a ghost marker on each peer's bar for comparison
- Hero row visually distinguished (slightly tinted background)
- Tooltip on subfield column headers (existing behavior, keep)

---

### Variant B — Subfield Radar Table

Layout: table, but the subfield citation columns are replaced by a single mini radar/spider chart per row.

**Columns:**
- Name + country tag + h-index (in small text below name)
- Career centroid bar (same as A)
- Radar cell: SVG pentagon/star chart with 5 axes (one per top subfield). Each peer's polygon is drawn in their accent color; hero's polygon overlaid as a dashed reference on each peer row. Scale: each axis independently normalized to global max for that subfield.
- Sparkline cell (same as A — cites only, wide)
- Papers | Citations stats

**Visual notes:**
- Radar size: ~72×72px per cell
- Hero row renders a solid filled polygon; other rows render a stroked polygon with hero ghost
- Axis labels (abbreviated subfield names) shown as tiny text at each vertex

---

### Variant C — Timeline Swimlane Table

Layout: table, but the sparkline column is replaced by a full-width horizontal timeline. The key feature is that all rows share the same time axis (aligned years), making temporal career comparison meaningful.

**Columns:**
- Name + country + h-index
- Subfield cells (same as current)
- Timeline cell (min-width: 200px, flex-grow): covers the full ERA window. Citation counts rendered as a vertical bar per year (bar chart style, not line). Hero bars shown in a distinct color; peer rows show peer bars with a translucent hero bar overlay for direct comparison. Career centroid marked as a vertical tick on the timeline.
- Papers | Citations stats

**Visual notes:**
- Bars are narrow (proportional to column width / 11)
- Hover on a bar shows year + count tooltip
- Color scheme: peer bars in primary color, hero overlay in a secondary contrasting color at 30% opacity

---

### Variant D — Portrait Card Grid

Layout: replaces the table entirely. A responsive grid of cards (2–3 per row on wide screens).

**Each card contains:**
- Header: name (link for peers, plain for hero), country tag, h-index badge
- Stat row: Papers · Citations · Career centroid indicator (inline dot bar)
- Subfield mini-bar chart: 5 horizontal bars, one per top subfield, normalized to hero's value. Bar length = peer_value / hero_value (capped at 2×). Hero card shows the absolute values as a reference.
- Sparkline: cites-only, spans full card width, height ~60px, with hero reference line on peer cards

**Visual notes:**
- Hero card is rendered first and visually distinct (border, background)
- Cards same fixed height; overflow handled with scroll on the card body if needed
- Subfield bars: label on left (abbreviated), bar in center, ratio (×1.3 etc.) on right

---

### Variant E — Dual-Panel: Overlay Chart + Compact Stat Table

Layout: two-panel split. Top panel is a shared overlay line chart of citation trends for all peers. Bottom panel is a compact table with no sparklines.

**Top panel (overlay chart):**
- Shared SVG chart, full component width, height ~160px
- One line per author (hero + all peers)
- X-axis: years (ERA_SIZE = 11 points), labeled at each end
- Y-axis: citation count, shared scale (global max)
- Hero line: thicker, distinct color, labeled at endpoint
- Peer lines: thinner, semi-transparent, colored by `careerCentroid` value (color gradient early→late), labeled at endpoint
- Hover interaction: highlight one line, show name + year + value tooltip

**Bottom panel (compact table):**
- Columns: Name + country | H-index | Career stage bar | Subfield citation cells (same as current) | Papers | Citations
- No sparkline column (handled by top panel)
- Clicking a row highlights the corresponding line in the top panel

---

## Comparison Page

A temporary route (e.g. `/peers-compare`) that fetches a single `EntityPeersResp` for a hardcoded or query-param author, then renders all five variants stacked vertically with labeled section headers (Variant A, B, C, D, E). No routing or navigation needed — just a scrollable page for visual comparison.

The existing `author-peers` endpoint and data pipeline feed all five variants identically.
