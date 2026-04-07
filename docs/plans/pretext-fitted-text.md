# Fitted Text: Performance and SVG Pain

## Problem

`BrokenFittedText` fits text at the largest possible font size into a given rectangle by splitting it across lines. Two issues:
1. **Performance** — `getStylesForWords` runs on every Svelte reactive update; it calls `formatTextToLinesOneWay` twice (horizontal + vertical orientation), each iterating up to 7 times.
2. **SVG text complexity** — placing broken text in SVG requires per-word transform strings, manual x/y offsets per line, and careful coordinate math. It's fragile and verbose.

## Why pretext doesn't help much here

[pretext](https://github.com/chenglou/pretext) is designed to replace DOM-based text measurement (avoiding `getBoundingClientRect` / `offsetHeight` reflows). The current implementation is already pure arithmetic — no DOM measurement — so that benefit doesn't apply. pretext also still returns line data that you have to place manually in SVG, so it doesn't reduce SVG text complexity either. Its canvas-based measurement would improve accuracy for variable-width fonts, but `BrokenFittedText` uses monospace (`var(--font-mono)`), where the `widthMultiplier: 0.6` heuristic is already accurate.

## Actual improvement paths

### 1. `<foreignObject>` — eliminates SVG text complexity entirely

Embed an HTML `<div>` inside SVG via `<foreignObject>`. The browser handles line breaking, font rendering, and alignment natively via CSS. To find the largest fitting font size, binary search over `font-size` values and use `scrollHeight <= height` to check fit — or use `canvas.measureText()` once at a base size and scale. This removes all per-word transform logic and the line-splitting code entirely.

Caveat: `<foreignObject>` has inconsistent behavior across browsers for SVG export / screenshot use cases. Worth checking if that matters here.

### 2. Memoization — addresses performance directly

The current computation is pure and deterministic: same `(text, width, height, anchor, bottomAligned, allowRotation, heightMultiplier, widthMultiplier)` always produces the same result. A `Map` keyed on `(text, width, height)` (the parameters that actually change per node) would avoid redundant work as tree nodes re-render during animations. Tree labels don't change, so cache hits would be frequent.

### 3. Replace the iteration with binary search

`formatTextToLinesOneWay` linearly increments `numOfLines` up to 7 times. Replacing with a binary search over `numOfLines` (range 1–`words.length`) converges in `log2(n)` steps. Combined with memoization, this matters only for texts with many words.
