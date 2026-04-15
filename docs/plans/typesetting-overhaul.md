# Typesetting Overhaul

## Type Scale (`:root` in `styles.css`)

Base: browser default `16px` on `html` (unchanged).

### Static tokens

```css
--text-2xs:  0.55rem;  /*  8.8px — badges, tiny labels */
--text-xs:   0.65rem;  /* 10.4px — secondary meta, details */
--text-sm:   0.75rem;  /* 12px   — UI controls, table cells */
--text-base: 0.85rem;  /* 13.6px — body prose */
--text-md:   1rem;     /* 16px   — lede, emphasis */
--text-lg:   1.15rem;  /* 18.4px — h3, section lead-ins */
--text-xl:   1.35rem;  /* 21.6px — h2 */
--text-2xl:  1.7rem;   /* 27.2px — h1 page titles */
```

### Viewport-responsive tokens

For elements that must scale on narrow viewports (<500px). All cap at ~500px — above that they equal the static token.

```css
--text-sm-vw:   min(var(--text-sm),   2.4vw);
--text-base-vw: min(var(--text-base), 2.7vw);
--text-md-vw:   min(var(--text-md),   3.2vw);
--text-lg-vw:   min(var(--text-lg),   3.7vw);
```

Utility classes `.vw-sm`, `.vw-base`, `.vw-md`, `.vw-lg` reference these. Used in constrained containers (info panels, visualization captions, form controls that appear alongside SVG).

Components can also use `var(--text-base-vw)` directly in scoped CSS instead of the class.

### Line-height tokens

```css
--lh-heading: 1.2;
--lh-body:    1.6;
--lh-ui:      1.3;
```

### Global heading defaults

```css
h1 { font-size: var(--text-2xl); line-height: var(--lh-heading); margin: 0; }
h2 { font-size: var(--text-xl);  line-height: var(--lh-heading); margin-bottom: 8px; }
h3 { font-size: var(--text-lg);  line-height: var(--lh-heading); text-align: center; }
```

### Semantic aliases

`--control-bar-font: var(--text-sm)` — for control bars (PaperRainbow, Toc, PathLevelInfoBox).

### Wide-screen step-up pattern

DagChip, ImpactDag, ExportControls, AllWorks, EntityPeers use `@media (min-width: 1200px)` to step up 1–2 token levels on wide screens. This is component-local, not a global system.

---

## What is left alone

- **BrokenFittedText** — `baseFontSize: 10` is SVG transform coordinates.
- **SVG visualization text** (ScrollyCGraph, TimelineViz, PaperRainbow viewBox units, Range, TickBars, YearTicks) — computed from container geometry.
- **Landing page hero** (56px h1, 32px section h2, 36px responsive h1) — intentional large display type.
- **TreeSvg / WorldMapSvg `12px`** — SVG-specific.
- **PeersB radar label `7px`** — SVG radar chart labels.
- **Layout close-icon / search-input `22px`** — intentional UI element sizing.
- **MidpathBar `min(1.5rem, 3.5vw)`** — one-off between `--text-xl` and `--text-2xl`.

---

## Open question

**Monospace for prose** — Courier New is fine for data labels. For the abstract and "About" paragraphs on hit-paper pages, a narrow sans-serif would improve readability significantly. This requires adding `--font-prose` and a second font family. Highest-leverage UX change but most visible departure from the current aesthetic.
