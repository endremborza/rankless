# To-do — Frontend & UI

Remaining frontend work. Delete a section when it lands.

Sections:

- [Fitted-text performance & SVG simplification](#fitted-text-performance--svg-simplification)
- [Monospace for prose](#monospace-for-prose)

---

## Fitted-text performance & SVG simplification

`BrokenFittedText` fits text at the largest font size into a rectangle by splitting it
across lines. Two issues:

1. **Performance** — `getStylesForWords` runs on every reactive update; it calls
   `formatTextToLinesOneWay` twice (horizontal + vertical), each iterating up to 7×.
2. **SVG complexity** — broken text in SVG needs per-word transform strings, manual x/y
   offsets per line, fragile coordinate math.

`pretext` doesn't help much: the current code is already pure arithmetic (no DOM
measurement, so no reflow benefit), still returns line data you place manually (no SVG
simplification), and the monospace `widthMultiplier: 0.6` heuristic is already accurate.

Improvement paths:

- **`<foreignObject>`** — embed an HTML `<div>`; the browser handles line breaking, fonts,
  alignment via CSS. Binary-search `font-size` using `scrollHeight <= height` (or
  `canvas.measureText()` once and scale). Removes all per-word transform + line-splitting
  logic. Caveat: `<foreignObject>` behaves inconsistently across browsers for SVG
  export/screenshot — check whether that matters here.
- **Memoization** — the computation is pure: same `(text, width, height, anchor,
bottomAligned, allowRotation, heightMultiplier, widthMultiplier)` → same result. A `Map`
  keyed on `(text, width, height)` would avoid redundant work as tree nodes re-render during
  animations (labels don't change → frequent hits).
- **Binary search** — replace `formatTextToLinesOneWay`'s linear `numOfLines` increment
  (up to 7) with binary search over `numOfLines` (1–`words.length`), `log2(n)` steps.
  Combined with memoization, matters only for many-word texts.

---

## Monospace for prose

The type scale (`--text-*`, `--text-*-vw`, `--lh-*` tokens, `.vw-*` utilities, per-component
wide-screen step-ups) is implemented in `src/routes/styles.css`. One open question remains:

Courier New is fine for data labels, but the abstract and "About" paragraphs on hit-paper
pages would read significantly better in a narrow sans-serif. This means adding a
`--font-prose` token and a second font family — the highest-leverage UX change, but the most
visible departure from the current monospace aesthetic. Decide before implementing.
