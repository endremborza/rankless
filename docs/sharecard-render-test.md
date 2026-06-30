# Share-card (OG image) render test protocol

Goal: verify whether a Rankless entity page produces a working social **share card**. Most of
this is automated by **`pyscripts/sharecard_test.py`**; the small residual that can't be — a human
confirming a real platform renders the image — is at the end.

## Background — current wiring

- `src/routes/(stat)/[rootType]/[...semanticId]/+page.svelte` emits `og:image` = `data.svgLink`,
  `twitter:card` = `summary`, `og:title`, `twitter:creator=@LearningCCL`, `description`.
- `data.svgLink` (`…/+page.server.ts`) = absolute URL of `/pic/{rootType}/{…}/breakdown.svg`.
- that route (`…/breakdown.svg/+server.ts`) serves **`Content-Type: image/svg+xml`**.

**Hypothesis:** X, LinkedIn, Facebook, Slack, Discord, WhatsApp, iMessage **do not render SVG OG
images** (they require PNG/JPEG), so the card is blank everywhere. Secondary: `summary` yields a
tiny thumbnail even with a valid raster. Crawlers can't reach `localhost`, so all tests run against
a **public URL** (the live site, or a tunnel: `cloudflared tunnel --url http://localhost:5173`).

## Automated — `pyscripts/sharecard_test.py`

```sh
uv run -m pyscripts.sharecard_test https://rankless.org/institutions/<slug>
```

Fetches the page **as a social crawler** (`--ua facebook|twitter|linkedin|browser`), extracts every
`og:`/`twitter:` tag, downloads the `og:image`, and runs the checklist below. **Exits non-zero on any
FAIL**, so it doubles as a pre-launch gate / CI check.

| Check                  | Pass condition                                                                                      |
| ---------------------- | --------------------------------------------------------------------------------------------------- |
| `og:image present`     | tag exists                                                                                          |
| `og:image fetchable`   | downloads OK (reports size + load time)                                                             |
| `og:image is raster`   | content-type is PNG/JPEG/WebP (**SVG ⇒ FAIL** — the blocker)                                        |
| `twitter:card`         | `summary_large_image` (`summary` ⇒ WARN)                                                            |
| `dimensions ~1200x630` | within ±15% (reads PNG/JPEG/SVG headers, no Pillow dep)                                             |
| `size < 5 MiB`         | byte size under the platform limit                                                                  |
| `loads < 2s`           | fetch latency                                                                                       |
| `recommended tags`     | `og:image:width/height/type`, `og:url`, `og:description`, `twitter:title/description/image` present |

**Flags:**

- `--rasterize [--out card.png] [--width --height]` — fetches the `og:image` and, if it's SVG,
  converts it to a 1200×630 PNG via `rsvg-convert` (same path as `pyscripts/svg_export.py`). Host
  that PNG and you can prove a raster card _does_ render. Needs `rsvg-convert`
  (`brew install librsvg` / `apt-get install librsvg2-bin`).
- `--fb-token <token>` — runs the **live Facebook scrape** (`graph.facebook.com/?id=…&scrape=true`)
  and prints what their crawler resolves.

Pre-fix output against production (the hypothesis the fix addresses):

```
✓ PASS  og:image present: …/pic/institutions/<slug>/breakdown.svg
✓ PASS  og:image fetchable: 15 KiB in 0.16s
✗ FAIL  og:image is raster: image/svg+xml — SVG is NOT rendered by X/LinkedIn/Facebook/Slack…
! WARN  twitter:card: summary → small square; use summary_large_image for a banner
! WARN  dimensions ~1200x630: 190x100
✓ PASS  size < 5 MiB: 0.01 MiB
✓ PASS  loads < 2s: 0.16s
! WARN  recommended tags: missing: og:image:width, …, twitter:image
```

The fix below ships in the code; this run should exit 0 against a deploy that has it (the deploy host
needs `librsvg2-bin`). Re-run after deploying and do the manual residual once.

## Manual residual (can't be automated)

1. **Eyes on a real platform.** Open the links the script prints and confirm the image actually
   renders (the script verifies the _bytes/headers_ a crawler gets; only a human sees the rendered
   card). Quick targets: a private Slack/Discord DM, the X compose box on a throwaway account,
   LinkedIn Post Inspector, Facebook Sharing Debugger.
2. **Proof (optional).** Run `--rasterize`, host the PNG, point a throwaway page's `og:image` at it,
   re-check via the same validators → renders large ⇒ format confirmed as the cause.
3. **Cache busting after a fix.** LinkedIn Post Inspector "Inspect" again; FB Sharing Debugger
   "Scrape Again" — both cache hard and will keep showing the old blank card otherwise.
4. **Legibility at thumbnail size.** Shrink the rendered card to ~30% and confirm the entity
   **name**, one **headline number**, the **Rankless** wordmark, and `rankless.org` are all readable
   — not a dense breakdown tree shrunk to mush.

## The fix (as built)

Implemented as a sibling **`/pic/{rootType}/{…}/breakdown.png`** route:

- `lib/server/share-card.ts` — `buildBreakdownSvg` (the SVG build, factored out of `breakdown.svg`
  so both endpoints share one path) + `getBreakdownPng` (cache → build → rasterize).
- `lib/server/card-raster.ts` — `rasterizeSvg` shells `rsvg-convert` to a 1200×630 PNG (same tool as
  `pyscripts/svg_export.py`, no new npm dep) + a best-effort disk cache (`CARD_CACHE_DIR`, default
  `$TMPDIR/rankless-cards`) so a widely-shared card isn't re-rendered per crawler hit. A cache
  read/write failure never breaks serving; an arbitrary entity's card renders on first hit.
- The entity-page `<svelte:head>` points `og:image`/`twitter:image` at the `.png`, sets
  `twitter:card=summary_large_image`, and adds `og:url`/`og:description`/`og:type`/`og:site_name` +
  `og:image:width/height/type` + `twitter:title/description`.
- `buildBreakdownSvg` turns every failure into a clean **404, never a 500**: unknown root type (a bot
  hitting `/pic/<garbage>/…` would otherwise index `undefined` in `parseLinkWithParams`), a non-OK
  backend response, or a malformed/missing entity. Both endpoints inherit this via the shared helper.

`rasterizeSvg` + cache are unit-tested in `card-raster.test.ts` (PNG magic + 1200×630 dims, no
backend). **Deploy dependency:** `rsvg-convert` (`librsvg2-bin`) is in `pyscripts/deploy.py` `APTS`
(baked into fresh images); for the already-running box run `deploy.install_apts_live()` once. **Gate
after deploy:** `sharecard_test.py` exits 0 + manual residual.

If the full breakdown tree is too busy at card size (it renders at ~190×100 today), the follow-up is a
purpose-built card layout rendered through the same SVG→PNG path.
