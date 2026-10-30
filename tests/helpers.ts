import { type Page, expect, test } from '@playwright/test';
import { XMLParser } from 'fast-xml-parser';
import dev from '../src/lib/assets/data/dev.json' with { type: 'json' };
import { PORT } from '../src/lib/wire/rankless_server/consts';

export const BASE_URL = `http://localhost:${dev.previewPort}`;
export const BE_URL = process.env.BE_URL || `http://127.0.0.1:${PORT}/v1`;
export const YEAR_SELECT = '#impact select[aria-label="Since year"]';
export const BREAKDOWN_SELECT = '#impact .sentenceline select';
// The tree draws its branches with a 0.8s geometry transition.
const BRANCH_SETTLE_MS = 1000;

// First `limit` entity pathnames from a type's live sitemap. The e2e specs all need this; the array
// coercion handles single-entry sitemaps that fast-xml-parser unwraps into an object.
export async function sitemapEntityUrls(type: string, limit = Infinity): Promise<string[]> {
	const res = await fetch(`${BASE_URL}/sitemap-entity-${type}-1.xml`);
	expect(res.ok, `sitemap-entity-${type}-1.xml returned ${res.status}`).toBeTruthy();
	const entries = new XMLParser().parse(await res.text())?.urlset?.url;
	const arr = Array.isArray(entries) ? entries : entries ? [entries] : [];
	return arr.slice(0, limit).map((u: { loc: string }) => new URL(u.loc).pathname);
}

// A branch is filled with a gradient keyed by its path in the tree, so a first-level branch's key is
// a bare dm id and deeper ones are hyphenated. Reading the keys left to right gives the order the
// tree is drawn in, without depending on label text or on how the labels are broken across lines.
export async function firstLevelOrder(page: Page): Promise<number[]> {
	return page.evaluate(() => {
		const prefix = "url('#path-grad-";
		return [...document.querySelectorAll(`#impact svg path[fill^="${prefix}"]`)]
			.map((p) => ({
				key: p.getAttribute('fill')!.slice(prefix.length, -2),
				x: p.getBoundingClientRect().left
			}))
			.filter(({ key }) => !key.includes('-'))
			.sort((a, b) => a.x - b.x)
			.map(({ key }) => Number(key));
	});
}

// An entity page with its tree controls drawn and its requests done.
export async function openTree(page: Page, url: string) {
	await page.goto(url, { waitUntil: 'load' });
	await page.waitForSelector(YEAR_SELECT, { timeout: 20_000 });
	await page.waitForLoadState('networkidle');
}

// The sitemap's first institution, opened by `openTree`; the test skips when there is none.
export async function openFirstInstitution(page: Page): Promise<string> {
	const [url] = await sitemapEntityUrls('institutions', 1);
	test.skip(!url, 'no institution sitemap entries');
	await openTree(page, url);
	return url;
}

// `firstLevelOrder` once the branches have stopped moving.
export async function settledOrder(page: Page): Promise<number[]> {
	await page.waitForTimeout(BRANCH_SETTLE_MS);
	return firstLevelOrder(page);
}

// Navigate each url until one renders `has`, returning that url (or null). Lets a spec find an entity
// that actually has a given section/chart — not every author has hit papers, every entity a chart, etc.
export async function firstUrlWith(
	page: Page,
	urls: string[],
	has: string,
	ready = '#overview h1',
	probeTimeout = 4000
): Promise<string | null> {
	for (const url of urls) {
		await page.goto(url, { waitUntil: 'load' });
		await page.waitForSelector(ready, { timeout: 20_000 });
		try {
			await page.waitForSelector(has, { timeout: probeTimeout });
			return url;
		} catch {
			/* this entity lacks `has`; try the next */
		}
	}
	return null;
}

// Hand-placed SVG text has no layout engine to keep labels apart, so they silently collide as data
// shifts. jsdom can't measure text — only a real browser knows the rendered boxes. Returns every pair
// of non-empty <text> nodes under `svgSelector` whose boxes overlap by more than `tol` px (anti-alias
// slack), each named. Point it at any chart's svg after driving the interaction that reveals labels.
export async function overlappingText(
	page: Page,
	svgSelector: string,
	tol = 0.5
): Promise<string[]> {
	return page.evaluate(
		({ sel, t }) => {
			const svg = document.querySelector(sel);
			if (!svg) return [`<no svg matched: ${sel}>`];
			const boxes = Array.from(svg.querySelectorAll('text'))
				.filter((el) => (el.textContent ?? '').trim().length > 0)
				.map((el) => ({ label: (el.textContent ?? '').trim(), r: el.getBoundingClientRect() }))
				.filter(({ r }) => r.width > 0 && r.height > 0);
			const hits: string[] = [];
			for (let i = 0; i < boxes.length; i++) {
				for (let j = i + 1; j < boxes.length; j++) {
					const a = boxes[i].r;
					const b = boxes[j].r;
					const dx = Math.min(a.right, b.right) - Math.max(a.left, b.left);
					const dy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
					if (dx > t && dy > t)
						hits.push(
							`"${boxes[i].label}" ∩ "${boxes[j].label}" (${Math.round(dx)}×${Math.round(dy)}px)`
						);
				}
			}
			return hits;
		},
		{ sel: svgSelector, t: tol }
	);
}
