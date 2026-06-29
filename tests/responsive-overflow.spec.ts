import { type Page } from '@playwright/test';
import { test, expect } from './coverage/fixtures';
import { sitemapEntityUrls } from './helpers';

// Guards against the recurring "layout breaks on a small screen" bug: at each phone/tablet width it
// loads the home page and one live instance of every root type, then asserts the document never grows
// wider than the viewport (no page-level horizontal scrollbar). On failure it names the widest
// offending elements so the culprit is obvious instead of needing a manual hunt.

const WIDTHS = [320, 375, 430, 768];
const HEIGHT = 900;
const TOL = 1; // sub-pixel rounding slack
const ROOT_TYPES = [
	'authors',
	'institutions',
	'sources',
	'countries',
	'subfields',
	'hit-papers'
] as const;

async function firstSitemapUrl(type: string): Promise<string> {
	const [url] = await sitemapEntityUrls(type, 1);
	expect(url, `no sitemap entries for ${type}`).toBeTruthy();
	return url;
}

// Elements whose right edge spills past the viewport, ignoring any clipped by an overflow-x ancestor
// (those can't push a page-level scrollbar). Widest first, capped — just enough to point at the cause.
async function overflowOffenders(page: Page): Promise<string[]> {
	return page.evaluate((tol) => {
		const clientW = document.documentElement.clientWidth;
		const describe = (el: Element) => {
			const cls =
				typeof el.className === 'string' && el.className.trim()
					? '.' + el.className.trim().split(/\s+/).join('.')
					: '';
			return el.tagName.toLowerCase() + (el.id ? `#${el.id}` : '') + cls;
		};
		const clippedX = (el: Element) => {
			for (let n = el.parentElement; n; n = n.parentElement) {
				const ox = getComputedStyle(n).overflowX;
				if (ox === 'auto' || ox === 'scroll' || ox === 'hidden') return true;
			}
			return false;
		};
		// content-visibility:hidden subtrees (e.g. a collapsed <details> dropdown) still report a box but
		// don't contribute to the page's scroll width — skip them so offenders point at the real cause.
		const visible = (el: Element) =>
			!('checkVisibility' in el) ||
			(el as { checkVisibility(o?: object): boolean }).checkVisibility({
				contentVisibilityAuto: true,
				visibilityProperty: true
			});
		const out: { sel: string; right: number }[] = [];
		for (const el of Array.from(document.body.querySelectorAll('*'))) {
			const r = el.getBoundingClientRect();
			if (r.width === 0 || r.height === 0) continue;
			if (r.right > clientW + tol && !clippedX(el) && visible(el))
				out.push({ sel: describe(el), right: Math.round(r.right) });
		}
		out.sort((a, b) => b.right - a.right);
		return out.slice(0, 6).map((o) => `${o.sel} [right ${o.right} > ${clientW}]`);
	}, TOL);
}

test.describe('No horizontal overflow on small screens', () => {
	const routes: { label: string; url: string }[] = [{ label: 'home', url: '/' }];

	test.beforeAll(async () => {
		for (const t of ROOT_TYPES) routes.push({ label: t, url: await firstSitemapUrl(t) });
	});

	for (const width of WIDTHS) {
		test(`viewport ${width}px`, async ({ browser }) => {
			const context = await browser.newContext({ viewport: { width, height: HEIGHT } });
			const page = await context.newPage();
			const failures: string[] = [];

			for (const { label, url } of routes) {
				await page.goto(url, { waitUntil: 'load' });
				if (url !== '/') await page.waitForSelector('#overview h1', { timeout: 20_000 });
				await page.waitForTimeout(300); // let async sections (peers, charts) settle

				const over = await page.evaluate(
					() => document.documentElement.scrollWidth - document.documentElement.clientWidth
				);
				if (over > TOL) {
					const offenders = await overflowOffenders(page);
					failures.push(`${label} (${url}): ${over}px too wide → ${offenders.join('; ')}`);
				}
			}

			await context.close();
			expect(failures, `\n${failures.join('\n')}`).toEqual([]);
		});
	}
});
