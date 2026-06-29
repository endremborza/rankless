import { test, expect } from './coverage/fixtures';
import { sitemapEntityUrls, firstUrlWith, overlappingText } from './helpers';

// Hand-placed SVG <text> has no layout engine, so chart labels silently collide as data shifts (a
// trajectory's value running into the y-axis labels, a hovered column's readout into a series tag…).
// jsdom can't measure text — only a real browser knows the boxes. For each chart below: find an entity
// that renders it, then assert no two <text> nodes overlap, at rest and while hovering each label
// trigger in turn (every hover repositions a value onto its line tip / into the cap band).

type OverlapChart = {
	name: string;
	type: string; // sitemap entity type to probe
	probes: number; // how many entities to try before skipping
	svg: string; // chart svg scanned for overlaps
	present: string; // selector proving the chart rendered (probe target)
	hover: string; // elements hovered one-by-one, each repositioning a label
	maxHovers?: number; // cap (PaperRainbow draws at most 15 papers)
	force?: boolean; // hover transparent hit-rects
};

const CHARTS: OverlapChart[] = [
	{
		name: 'PaperRainbow citation timeline',
		type: 'authors',
		probes: 12,
		svg: '#papers .plot svg',
		present: '#papers .plot svg',
		hover: '#paper-list li[data-index]',
		maxHovers: 15
	},
	{
		name: 'EntityHero decade chart',
		type: 'authors',
		probes: 6,
		svg: '#overview .era-chart svg',
		present: '#overview .era-chart svg rect',
		hover: '#overview .era-chart svg rect',
		force: true
	}
];

for (const c of CHARTS) {
	test(`${c.name}: hovering any label keeps chart text non-overlapping`, async ({ browser }) => {
		const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
		const page = await context.newPage();

		const found = await firstUrlWith(page, await sitemapEntityUrls(c.type, c.probes), c.present);
		test.skip(found === null, `no ${c.type} entity rendering ${c.name} in ${c.probes} probes`);
		await page.evaluate(() => document.fonts.ready);

		const failures: string[] = [];
		const atRest = await overlappingText(page, c.svg);
		if (atRest.length) failures.push(`at rest: ${atRest.join('; ')}`);

		const targets = page.locator(c.hover);
		const n = Math.min(await targets.count(), c.maxHovers ?? Infinity);
		for (let i = 0; i < n; i++) {
			await targets.nth(i).hover({ force: c.force ?? false });
			await page.waitForTimeout(80); // let the scroll-into-view debounce + re-render settle
			const over = await overlappingText(page, c.svg);
			if (over.length) failures.push(`hover ${i}: ${over.join('; ')}`);
		}

		await context.close();
		expect(failures, `\n${failures.join('\n')}`).toEqual([]);
	});
}
