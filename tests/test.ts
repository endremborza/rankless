import { expect, test, type Page } from '@playwright/test';
import fs from 'fs';

test.setTimeout(120_000); // allow plenty of time for full run

test('navigate all links and test map control states quickly', async ({ page }) => {
	const visitedPages = new Set<string>();
	const paragraphTexts = new Set<string>();
	const paragraphSources: Record<string, string> = {};
	const pagesToVisit = new Set<string>(['/']);

	await page.goto('/');
	const links = await page.$$eval('a[href]', (anchors) =>
		anchors
			.map((a) => a.getAttribute('href'))
			.filter((h): h is string => !!h && h.startsWith('/') && !h.startsWith('//'))
	);
	links.forEach((l) => pagesToVisit.add(l));
	for (const url of pagesToVisit) {
		if (visitedPages.has(url)) continue;
		visitedPages.add(url);
		await page.goto(url);

		const mapBlocks = await page.$$('#map-control-block');
		if (mapBlocks.length === 0) {
			await collectParagraphs(page, paragraphTexts, url, paragraphSources);
			continue;
		}

		for (const block of mapBlocks) {
			const dropdown = await block.$('.sel-base');
			const checkbox = await block.$('input[type="checkbox"]');

			let dropdownValues = [''];
			if (dropdown) {
				dropdownValues = await dropdown.$$eval('option', (opts) => opts.map((o) => o.value));
			}

			const checkboxStates = checkbox ? [false, true] : [false];

			for (const val of dropdownValues) {
				if (dropdown && val) {
					await dropdown.selectOption(val);
				}
				for (const state of checkboxStates) {
					if (checkbox) {
						const isChecked = await checkbox.isChecked();
						if (isChecked !== state) {
							await checkbox.setChecked(state);
						}
					}

					// Just give the browser a single microtask to process UI updates
					await page.waitForTimeout(10);

					await collectParagraphs(page, paragraphTexts, url, paragraphSources);
				}
			}
		}
	}
	fs.writeFileSync('logs/paragraph_texts.txt', Array.from(paragraphTexts).join('\n\n'));
});

async function collectParagraphs(
	page: Page,
	paragraphTexts: Set<string>,
	url: string,
	paragraphSources: Record<string, string>
) {
	const elems = url.split('/');
	if (elems.length > 2) {
		const uType = elems[1];
		if (paragraphSources[uType] == undefined) paragraphSources[uType] = elems[2];
		if (paragraphSources[uType] != elems[2]) return;
	}
	const texts = await page.$$eval('p', (ps) => ps.map((p) => p.innerText.trim()).filter(Boolean));
	texts.forEach((t) => paragraphTexts.add(t));
}

test('index page has expected h1', async ({ page }) => {
	await page.goto('/');
	await expect(page.getByText('Spotlights')).toBeVisible();
});
