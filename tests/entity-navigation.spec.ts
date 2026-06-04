import { type Page } from '@playwright/test';
import { expect, test } from './coverage/fixtures';
import { XMLParser } from 'fast-xml-parser';

// Exercises every root type through real in-app navigation, asserting that no page raises a Svelte
// runtime error (e.g. each_key_duplicate from repeated leader names) and that hit-paper abstracts
// load. Instances come from each type's live sitemap; a known duplicate-name subfield is
// force-included. Navigation is interleaved so each step crosses into a different entity type.

test.describe.configure({ timeout: 180_000 });

const ROOT_TYPES = [
	'authors',
	'institutions',
	'sources',
	'countries',
	'subfields',
	'hit-papers'
] as const;
const PER_TYPE = 2;
const FORCED: Partial<Record<(typeof ROOT_TYPES)[number], string[]>> = {
	subfields: ['/subfields/geophysics'] // two distinct authors share a name here → duplicate key
};

// Svelte runtime errors always link to svelte.dev/e/<code>; that plus a raw pageerror covers crashes.
const SVELTE_ERROR = /svelte\.dev\/e\/|each_key_duplicate/i;

async function sitemapUrls(type: string, n: number): Promise<string[]> {
	const res = await fetch(`http://localhost:4173/sitemap-entity-${type}-1.xml`);
	expect(res.ok, `sitemap-entity-${type}-1.xml returned ${res.status}`).toBeTruthy();
	const parsed = new XMLParser().parse(await res.text());
	const entries = parsed?.urlset?.url;
	const arr = Array.isArray(entries) ? entries : entries ? [entries] : [];
	return arr.slice(0, n).map((u: { loc: string }) => new URL(u.loc).pathname);
}

function errorSink(page: Page): string[] {
	const errors: string[] = [];
	page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
	page.on('console', (m) => {
		if (m.type() === 'error' && SVELTE_ERROR.test(m.text())) errors.push(`console: ${m.text()}`);
	});
	return errors;
}

// Inject + click an anchor so SvelteKit's router intercepts it: real client-side navigation, which
// re-renders the page component in place (the path that surfaces keyed-each and stale-state bugs).
async function clientNavigate(page: Page, url: string): Promise<void> {
	await page.evaluate((u) => {
		const a = document.createElement('a');
		a.href = u;
		a.textContent = 'nav';
		document.body.appendChild(a);
		a.click();
	}, url);
	await page.waitForFunction(
		(u) => decodeURIComponent(location.pathname) === decodeURIComponent(u),
		url,
		{ timeout: 20_000 }
	);
}

// Round-robin by index so consecutive entries are always different types (cross-type navigation).
function interleave(byType: Map<string, string[]>): string[] {
	const out: string[] = [];
	const max = Math.max(...[...byType.values()].map((v) => v.length));
	for (let i = 0; i < max; i++) {
		for (const t of ROOT_TYPES) {
			const list = byType.get(t) ?? [];
			if (i < list.length) out.push(list[i]);
		}
	}
	return out;
}

test('navigates across all entity types without runtime errors', async ({ page }) => {
	const errors = errorSink(page);

	const byType = new Map<string, string[]>();
	for (const t of ROOT_TYPES) {
		const forced = FORCED[t] ?? [];
		const fromMap = (await sitemapUrls(t, PER_TYPE)).filter((u) => !forced.includes(u));
		const merged = [...forced, ...fromMap];
		expect(merged.length, `not enough sitemap entries for ${t}`).toBeGreaterThanOrEqual(PER_TYPE);
		byType.set(t, merged);
	}

	const sequence = interleave(byType);
	let sawAbstractText = false;

	await page.goto('/');
	for (const url of sequence) {
		await clientNavigate(page, url);
		await expect(page.locator('#overview h1'), `hero did not render for ${url}`).toBeVisible({
			timeout: 20_000
		});

		if (url.startsWith('/hit-papers/')) {
			// The abstract section appears (loading or text), then must reach a terminal state — never
			// stuck on "loading…". OpenAlex lacks abstracts for some papers, so the only invariant is
			// that the pending indicator clears (text rendered, or section resolved away).
			await expect(page.locator('.abstract'), `abstract section absent for ${url}`).toBeAttached({
				timeout: 20_000
			});
			await expect(
				page.locator('.abstract-loading'),
				`abstract stuck on "loading…" for ${url}`
			).toHaveCount(0, { timeout: 20_000 });
			if ((await page.locator('.abstract-text').count()) > 0) sawAbstractText = true;
		}

		await page.waitForTimeout(150); // let any async Svelte render error surface
		expect(errors, `runtime error after navigating to ${url}`).toEqual([]);
	}

	expect(sawAbstractText, 'no sampled hit-paper rendered a loaded abstract').toBe(true);
});
