import { type Page, expect } from '@playwright/test';
import { XMLParser } from 'fast-xml-parser';

export const BASE_URL = 'http://localhost:4173';

// First `limit` entity pathnames from a type's live sitemap. The e2e specs all need this; the array
// coercion handles single-entry sitemaps that fast-xml-parser unwraps into an object.
export async function sitemapEntityUrls(type: string, limit = Infinity): Promise<string[]> {
	const res = await fetch(`${BASE_URL}/sitemap-entity-${type}-1.xml`);
	expect(res.ok, `sitemap-entity-${type}-1.xml returned ${res.status}`).toBeTruthy();
	const entries = new XMLParser().parse(await res.text())?.urlset?.url;
	const arr = Array.isArray(entries) ? entries : entries ? [entries] : [];
	return arr.slice(0, limit).map((u: { loc: string }) => new URL(u.loc).pathname);
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
