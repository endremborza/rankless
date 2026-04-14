# Typesetting Overhaul

## Motivation

The hit-paper page exposes the core problem clearly: the abstract `<h2>` is styled at `0.9rem opacity: 0.5` — same size as body text but faded — while the "About" `<h2>` below it inherits the browser's default `h2` size (~1.5em), producing a jarring jump. The abstract text (`0.9rem`, `line-height: 1.6`) and the "About" paragraph (no explicit size — inherits browser default via the `<div>`) render at visually distinct scales with no intentional relationship. The page reads as two disconnected regions.

This is symptomatic of a wider pattern: ~50+ scattered font-size values across ~25 files, no heading scale, no line-height tokens, and responsive sizing applied ad-hoc via `min(rem, vw)` in some places but not others.

---

## Current State Inventory

### Type-scale tokens (styles.css `:root`)
```
--text-xs:   0.65rem
--text-sm:   0.75rem
--text-base: 0.85rem
--control-bar-font: 0.82rem
```
No heading tokens. No line-height tokens. No font-weight tokens.

### Font family
Everything is `'Courier New', monospace` via `--font-mono` → `--font-body` → `:root { font-family }`.  
No variable-width font is defined or used anywhere.

### Heading sizes
No CSS rules for `h1`, `h2`, `h3` sizes in `styles.css` — all fall back to browser UA defaults (~2em, 1.5em, 1.17em). These clash visibly with the rem-based component sizing.

### Body text
No explicit `font-size` on `html` or `body` — defaults to browser 16px. All `rem` values compound from this.

### Responsive sizing
- Six utility classes (`.hover-xs` → `.hover-xl`, `.text-s`) use `min(rem, vw)` in styles.css.
- Two components apply `min()` directly: `WorkElem` (`min(0.85rem, 2.2vw)`) and `MidpathBar` (`min(1.5rem, 3.5vw)`).
- One media query reduces the landing-page hero h1 (56px → 36px at 540px).
- SVG visualizations compute sizes dynamically in JS from container dimensions — these are correct and intentional; not part of this overhaul.

### BrokenFittedText
Uses `baseFontSize: 10` as a coordinate unit for SVG transform scaling — not a display font size. This is correct; no change needed here.

### Hit-paper page (the triggering case)
| Element | Current style | Problem |
|---|---|---|
| `<h1>` paper title | Browser default ~2em | Fine but uncontrolled |
| `<h2>Abstract` summary | `0.9rem opacity:0.5` | Same size as body; invisible hierarchy |
| abstract `<p>` | `0.9rem line-height:1.6` | Fine readability but disconnected from below |
| `<h2>About` | Browser default ~1.5em | Jumps to 24px from 14.4px — jarring |
| "About" `<div>` content | Inherits browser body (~16px) | Larger than the abstract text above it |

---

## Goals

1. **Establish a coherent type scale** — a small set of CSS custom properties covering all sizes from caption to hero, with predictable ratios.
2. **Normalize headings** — explicit `h1`/`h2`/`h3` sizes that compose with the scale instead of fighting browser defaults.
3. **Consistent line-height** — one value for body prose, one for UI labels, one for headings.
4. **Fix hit-paper page hierarchy** — abstract and "About" sections should read as a continuous, unified block.
5. **Retire scattered hardcoded sizes** — replace component-local `0.68rem`, `0.72rem`, `0.78rem`, etc. with scale tokens.
6. **Simplify responsive sizing** — keep `min()` for the handful of truly viewport-constrained elements; remove it where the rem value alone is sufficient.

---

## Proposed Type Scale

Base: `font-size: 15px` on `html` (currently inherited browser 16px — minor shift, avoids ugly sub-pixel rem fractions).

```css
--text-2xs:  0.6rem;   /* 9px  — tiny labels, SVG captions */
--text-xs:   0.7rem;   /* 10.5px — secondary meta */
--text-sm:   0.8rem;   /* 12px  — UI labels, table cells */
--text-base: 0.9rem;   /* 13.5px — body prose */
--text-md:   1rem;     /* 15px  — default, lede */
--text-lg:   1.15rem;  /* 17px  — h3, section lead */
--text-xl:   1.35rem;  /* 20px  — h2 */
--text-2xl:  1.7rem;   /* 25.5px — h1 page titles */
```

And heading defaults in `styles.css`:
```css
h1 { font-size: var(--text-2xl); line-height: var(--lh-heading); margin: 0; }
h2 { font-size: var(--text-xl);  line-height: var(--lh-heading); margin-bottom: 8px; }
h3 { font-size: var(--text-lg);  line-height: var(--lh-heading); text-align: center; }
```

Line-height tokens:
```css
--lh-heading: 1.2;
--lh-body:    1.6;
--lh-ui:      1.3;
```

This replaces and supersedes the current `--text-xs/sm/base` tokens.

The landing-page hero h1 (`56px` / `36px`) and section h2 (`32px`, `22px`) are intentional large-display sizes — keep them as explicit px overrides on those specific elements, not part of the base scale.

---

## Hit-Paper Page Fix

The abstract and about sections should share the same typographic register: both are prose, both are medium-length, both need to be read in sequence.

**Specific changes to `+page.svelte` (`[rootType]/[...semanticId]/`):**

```css
/* replace current */
#abstract summary h2 { font-size: 0.9rem; opacity: 0.5; }
#abstract p { font-size: 0.9rem; line-height: 1.6; opacity: 0.85; }

/* with */
#abstract summary h2 { font-size: var(--text-sm); opacity: 0.55; font-weight: normal; }
#abstract p { font-size: var(--text-base); line-height: var(--lh-body); opacity: 0.85; }
```

Remove the override that makes the `#abstract h2` the same size as body text — the distinction should come from opacity and font-weight, not from making the label microscopic.

The `#about > div` content will now inherit `--text-base` naturally from the scale. The `h2` headings throughout the page will be `--text-xl` (1.35rem), visually above prose without being browser-default-huge.

---

## Component Migration Plan

Priority order based on user-facing impact:

### Phase 1 — Tokens and global baseline
1. Update `styles.css` `:root`: add new tokens, add `html { font-size: 15px }`, define `h1/h2/h3` rules, add `--lh-*` tokens.
2. Audit existing uses of `--text-xs/sm/base` — remap to new tokens (values shift slightly).

### Phase 2 — Hit-paper page
3. Fix `[rootType]/[...semanticId]/+page.svelte` abstract/about typography (as above).
4. Check `+layout.svelte` heading overrides (`22px` h2, `22px` nav-item) — replace with `--text-xl` or `--text-2xl` as appropriate.

### Phase 3 — High-impact components
5. `DagChip.svelte` — 8 distinct font sizes (0.55–1.15rem); consolidate to 3–4 scale tokens.
6. `ImpactDag.svelte` — 7 distinct sizes; consolidate.
7. `PaperRainbow.svelte` — 6 distinct sizes; consolidate.
8. `ExportControls.svelte` — 6 distinct sizes; consolidate.
9. `EntityPeers.svelte` — 5 distinct sizes; consolidate.

### Phase 4 — Remaining components
10. `WorkElem`, `AllWorks`, `RefTreeTable`, `HitPaperBreakdown`, `SearchResults`, `HoverI`, `HitPaperExplainer`, `SurveyPrompt`, `MidpathBar`, `TextedLogo`.
11. Route pages: `path-to-person`, `survey`, `table`.

### Phase 5 — Responsive simplification
12. Audit all `min(rem, vw)` uses. Remove any where the rem cap is never reached at realistic viewport widths (e.g. `.hover-xs: min(0.75rem, 1.5vw)` — at 1.5vw = 0.75rem the viewport is exactly 800px; fine to keep). The `.text-s` class (`min(0.85rem, 3vw)`) should be eliminated in favour of a scale token.
13. `WorkElem`'s inline `min(0.85rem, 2.2vw)` and `MidpathBar`'s `min(1.5rem, 3.5vw)` — evaluate against new scale; simplify if viewport scaling is not visibly necessary.

---

## What to Leave Alone

- **BrokenFittedText / text-format-util** — `baseFontSize: 10` is an SVG transform coordinate, not a display size. The memoization improvement is tracked in `pretext-fitted-text.md`.
- **SVG visualization text** (`ScrollyCGraph`, `TimelineViz`, `PaperRainbow` viewBox units, `Range`, `TickBars`, `YearTicks`) — these compute from container geometry; a CSS type scale cannot govern them.
- **Landing-page hero** — intentionally large display type; keep explicit px overrides.
- **`TreeSvg` / `WorldMapSvg` `font-size: 12px`** — SVG-specific; leave as is.

---

## Open Questions

1. **Monospace for prose** — Courier New is fine for data labels and code-adjacent UI. Is it still the intent for the abstract and "About" paragraph? A narrow sans-serif for long-form prose would improve readability significantly, but requires adding a second font family and introducing `--font-prose`. This is the highest-leverage UX change but also the most visible departure from the current aesthetic. Decide before Phase 2.

2. **Base font-size** — changing from browser-default 16px to 15px shifts all `rem` values slightly. The current `--text-base: 0.85rem` (13.6px at 16px base) becomes `--text-base: 0.9rem` (13.5px at 15px base) — nearly identical absolute size. If the 15px base is disruptive, stay at 16px and adjust token values instead.
