# Share-card (OG image) render test protocol

Goal: verify whether a Rankless entity page produces a working social **share card**. Most of
this is automated by **`pyscripts/sharecard_test.py`**; the small residual that can't be — a human
confirming a real platform renders the image — is at the end.

## Background — the wiring

- `src/routes/(stat)/[rootType]/[...semanticId]/+page.svelte` emits `og:image` and `twitter:image` = `data.pngLink`, `twitter:card` = `summary_large_image`, `og:title`, `twitter:creator=@LearningCCL`, `description`.
- `data.pngLink` (`…/+page.server.ts`) = absolute URL of `/card/{rootType}/{…}/tree.png`.
- that route serves **`Content-Type: image/png`**.

X, LinkedIn, Facebook, Slack, Discord, WhatsApp, iMessage **do not render SVG OG images** (they require PNG/JPEG), and `summary` yields a tiny thumbnail even with a valid raster, which is why the card is a PNG under `summary_large_image`. Crawlers can't reach `localhost`, so all tests run against a **public URL** (the live site, or a tunnel to the dev server: `cloudflared tunnel --url http://localhost:<devPort>`, `devPort` in `src/lib/assets/data/dev.json`).

## Automated — `pyscripts/sharecard_test.py`

```sh
uv run -m pyscripts.sharecard_test https://rankless.org/institutions/<slug>
```

Fetches the page **as a social crawler** (`--ua facebook|twitter|linkedin|browser`), extracts every
`og:`/`twitter:` tag, downloads the `og:image`, and runs the checklist below. **Exits non-zero on any
FAIL**, so it doubles as a pre-launch gate / CI check.

| Check | Pass condition |
| --- | --- |
| `og:image present` | tag exists |
| `og:image fetchable` | downloads OK (reports size + load time) |
| `og:image is raster` | content-type is PNG/JPEG/WebP (**SVG ⇒ FAIL** — the blocker) |
| `twitter:card` | `summary_large_image` (`summary` ⇒ WARN) |
| `dimensions ~1200x630` | within ±15% (reads PNG/JPEG/SVG headers, no Pillow dep) |
| `size < 5 MiB` | byte size under the platform limit |
| `loads < 2s` | fetch latency |
| `recommended tags` | `og:image:width/height/type`, `og:url`, `og:description`, `twitter:title/description/image` present |

**Flags:**

- `--rasterize [--out card.png] [--width --height]` — fetches the `og:image` and, if it's SVG,
  converts it to a 1200×630 PNG via `rsvg-convert`. Host
  that PNG and you can prove a raster card _does_ render. Needs `rsvg-convert`
  (`brew install librsvg` / `apt-get install librsvg2-bin`).
- `--fb-token <token>` — runs the **live Facebook scrape** (`graph.facebook.com/?id=…&scrape=true`)
  and prints what their crawler resolves.

The run exits 0 against a deploy (the deploy host needs `librsvg2-bin`). Re-run after deploying and do the manual residual once.

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
   **name**, the **caption**, the **Rankless** wordmark, and `rankless.org` are all readable
   — not a dense breakdown tree shrunk to mush.

## The card (as built)

The entity page's `og:image`/`twitter:image` point at **`/card/{rootType}/{…}/tree.png`** (with the page's `?tree=&since=&paths=` view state), `twitter:card=summary_large_image`, and the `og:url`/`og:description`/`og:type`/`og:site_name` + `og:image:width/height/type` + `twitter:title/description` tags are set. The route is one of the share-card family described in `architecture.md` (`lib/server/cards/`): the kind's loader turns the URL's variant parameters into backend calls (a malformed parameter, an unknown root type or a backend failure is a clean **404, never a 500**, since crawlers hit stale and garbage URLs), `CardFrame.svelte` wraps the kind's pure-SVG component, `svelte/server` renders it, and `lib/server/card-raster.ts` shells `rsvg-convert` to a 1200×630 PNG (no npm dep) behind a best-effort disk cache (`CARD_CACHE_DIR`, default `$TMPDIR/rankless-cards`) so a widely shared card is not re-rendered per crawler hit.

Every card, the homepage one included (`HomeCard.svelte` → `card/home.png`), is typeset in the brand faces — **Hedvig Letters Serif**, **Hedvig Letters Sans**, **Space Mono** (`lib/utils/cards.ts` names them with their generic fallbacks). `rsvg-convert` resolves fonts via **fontconfig, not browser web-fonts**, so the faces are vendored in `static/fonts/` (OFL) and `deploy.py` `install_fonts()` copies them into the runner's user font dir + `fc-cache` on every FE deploy. Two rasterizer facts shape every card component: it does not resolve CSS `var()` (a colour through a variable renders black), and a component `<style>` never reaches the server-rendered markup, so cards carry literal colours and inlined face attributes and estimate text widths from character counts.

`rasterizeSvg` + cache are unit-tested in `card-raster.test.ts` (PNG magic + 1200×630 dims, no backend). **Deploy dependency:** `rsvg-convert` (`librsvg2-bin`) + `fontconfig` are in `pyscripts/deploy.py` `APTS`. **Gate after deploy:** `sharecard_test.py` exits 0 + manual residual.
