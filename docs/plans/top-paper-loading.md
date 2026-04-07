# Top Paper Loading Rework

## Root causes

1. **No persistence** — `paperCache` is an in-memory `Map`; lost on every navigation. Every session cold-fetches from OpenAlex even for papers viewed before.
2. **Mobile preload disabled** — `preloadArmedPaper` bails if `!hasSpaceForPaper` (i.e. on mobile). Arm events rarely fire on touch anyway, so there is no preload path on mobile at all.
3. **Preload only on arm, not on highlight** — when a path is selected (click/tap), `highlightedPath` updates but the paper isn't prefetched until the user also hovered first. On first interaction the paper always loads cold.
4. **`WorkElem` mount guard** — `updateByWorkId` skips the fetch when `!mounted` (correct), but `onMount` fires after the first paint. Since `containerWidth` also needs a paint cycle before `hasSpaceForPaper` is true, the auto-show and fetch both lag one render cycle on desktop.

## Changes

### 1. localStorage paper cache (`src/lib/stores.ts`)
- On module init (`browser` guard for SSR safety): read `rankless:papers` from localStorage, populate `paperCache`.
- After each successful fetch, serialize `paperCache` back to localStorage.
- Limit to 300 entries; if exceeded, drop the oldest (slice the entries array).
- Errors (quota exceeded, corrupted JSON) are silently swallowed.

### 2. Preload on leaf highlight (`src/lib/components/PathLevelInfoBox.svelte`)
- Add reactive statement `$: if (leaf?.topSourceId) prefetchPaper(leaf.topSourceId)`.
- Fires whenever the highlighted leaf changes (path selected or hovered), ensuring the paper is fetched immediately — before the user clicks "Show top paper" on mobile.

### 3. Remove `hasSpaceForPaper` guard from arm preload
- `preloadArmedPaper` currently bails if `!hasSpaceForPaper`. Remove that guard.
- Low-cost change: arm events are rare on touch, but this keeps the desktop arm-preload working regardless of measured width.
