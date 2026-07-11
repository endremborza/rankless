// Cold-crawler-shaped FE load generator (companion to pyscripts/stress.py).
//
//   node pyscripts/fe_browser_load.mjs <corpus.gz> [contexts] [minutes]
//   BASE=http://127.0.0.1:14003 node pyscripts/fe_browser_load.mjs authors.gz 6 30
//
// Why a real browser and not curl/httpx: curl fetches only the SSR HTML (1 request
// to bun). A browser fetches the full ~52-request fan-out (HTML + 51 `_app` assets),
// hydrates, and on client-side navigation fires the server `__data.json` load — the
// paths a JS-executing crawler exercises and a flat GET never does. Each context is
// recycled after a few pages so its cache goes cold again (crawlers arrive cold; a
// warm browser would cache the immutable assets and stop hitting bun for them).
//
// Point BASE at an SSH tunnel onto ONE bun worker (see stress.py `feleak`) to isolate
// it; sample its cgroup RSS separately (`stress sample` / feleak's sampler).

import { chromium } from "@playwright/test";
import { readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";

const BASE = process.env.BASE || "http://127.0.0.1:14003";
const CORPUS = process.argv[2];
const CONTEXTS = parseInt(process.argv[3] || "6", 10);
const MINUTES = parseFloat(process.argv[4] || "30");
const PAGES_PER_CONTEXT = 8; // then recycle the context -> cold cache again

if (!CORPUS) {
  console.error("usage: node fe_browser_load.mjs <corpus.gz> [contexts] [minutes]");
  process.exit(1);
}

const raw = CORPUS.endsWith(".gz")
  ? gunzipSync(readFileSync(CORPUS)).toString()
  : readFileSync(CORPUS, "utf8");
const byKind = {};
for (const ln of raw.split("\n")) {
  const i = ln.indexOf("/");
  if (i > 0) (byKind[ln.slice(0, i)] ||= []).push(ln.slice(i + 1));
}
const kinds = Object.keys(byKind).filter((k) => byKind[k].length > 10);
console.log("kinds:", kinds.map((k) => `${k}:${byKind[k].length}`).join(" "));

const rand = (a) => a[Math.floor(Math.random() * a.length)];
const deadline = Date.now() + MINUTES * 60000;
const stats = { loads: 0, navs: 0, errors: 0 };

async function contextLoop(browser) {
  while (Date.now() < deadline) {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    for (let i = 0; i < PAGES_PER_CONTEXT && Date.now() < deadline; i++) {
      const kind = rand(kinds);
      try {
        await page.goto(`${BASE}/${kind}/${rand(byKind[kind])}`, {
          waitUntil: "load",
          timeout: 30000,
        });
        stats.loads++;
        // best-effort client-side nav -> SvelteKit intercepts -> __data.json
        if (Math.random() < 0.5) {
          const sel =
            'a[href^="/authors/"],a[href^="/institutions/"],' +
            'a[href^="/sources/"],a[href^="/hit-papers/"]';
          const link = page.locator(sel).filter({ visible: true }).first();
          if (await link.count()) {
            await link.click({ timeout: 5000 });
            await page.waitForLoadState("load", { timeout: 20000 });
            stats.navs++;
            stats.loads++;
          }
        }
      } catch {
        stats.errors++;
      }
    }
    await ctx.close();
  }
}

const browser = await chromium.launch({
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});
const t0 = Date.now();
const reporter = setInterval(() => {
  const s = (Date.now() - t0) / 1000;
  console.log(
    `t=${Math.round(s)}s loads=${stats.loads} navs=${stats.navs} ` +
      `errors=${stats.errors} rps=${(stats.loads / s).toFixed(1)}`,
  );
}, 20000);
await Promise.all(Array.from({ length: CONTEXTS }, () => contextLoop(browser)));
clearInterval(reporter);
await browser.close();
console.log(`done: loads=${stats.loads} navs=${stats.navs} errors=${stats.errors}`);
