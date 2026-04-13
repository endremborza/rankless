# EntityPeers Component Redesign

## Remaining: Pick a winner

All five variants (A–E) are rendered on the author entity detail page (`/authors/{semanticId}#peers`) stacked vertically for comparison.

After picking a favourite, the other four should be deleted and `EntityPeers.svelte` replaced with the chosen variant (or updated to match it).

The original `EntityPeers.svelte` is still present and can be used as reference.

---

## Files added

- `src/lib/peers-utils.ts` — shared utilities (paths, colors, radar math)
- `src/lib/components/PeersA.svelte` — Enhanced Table (h-index, career bar, country, wider sparkline)
- `src/lib/components/PeersB.svelte` — Radar Table (pentagon per row, hero ghost overlay)
- `src/lib/components/PeersC.svelte` — Timeline Swimlane (bar chart, hero overlay, centroid tick)
- `src/lib/components/PeersD.svelte` — Portrait Card Grid (responsive grid, subfield bars)
- `src/lib/components/PeersE.svelte` — Dual-Panel (overlay line chart + compact table, click-to-highlight)
