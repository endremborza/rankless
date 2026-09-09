import { type Page } from '@playwright/test';
import { test, expect } from './coverage/fixtures';
import { sitemapEntityUrls } from './helpers';

const OA_WORK_ROUTE = '**/api.openalex.org/works/**';

// An authorship OpenAlex never matched to an author entity carries a null author.id, next to a
// matched one that does get a profile link.
const WORK_JSON = {
	title: 'Third assessment report of the IPCC',
	publication_year: 2002,
	doi: null,
	authorships: [
		{ author: { id: null, display_name: 'Australia' }, institutions: [] },
		{
			author: { id: 'https://openalex.org/A5079108119', display_name: 'Uzbekistan' },
			institutions: []
		}
	]
};

async function openPaperBox(page: Page, urls: string[]) {
	for (const url of urls) {
		await page.goto(url, { waitUntil: 'load' });
		try {
			await page.waitForSelector('.paper-container h2, .paper-container h4', { timeout: 8000 });
			return page.locator('.paper-container').first();
		} catch {
			/* this entity's opening path has no top paper; try the next */
		}
	}
	throw new Error('no entity rendered a top-paper box');
}

test.describe('Top paper', () => {
	let entityUrls: string[];

	test.beforeAll(async () => {
		entityUrls = await sitemapEntityUrls('authors', 4);
	});

	test('renders a work whose authors OpenAlex never matched', async ({ browser }) => {
		const context = await browser.newContext({ viewport: { width: 1600, height: 900 } });
		const page = await context.newPage();
		await page.route(OA_WORK_ROUTE, (route) => route.fulfill({ json: WORK_JSON }));

		const box = await openPaperBox(page, entityUrls);
		await expect(box.getByRole('link', { name: /Third assessment report/ })).toBeVisible();
		await expect(box.getByText('Uzbekistan')).toHaveAttribute('href', '/oa-id/A5079108119');
		await expect(box.getByText('Australia')).not.toHaveAttribute('href', /./);
		await context.close();
	});

	test('falls back to an OpenAlex link when the work never loads', async ({ browser }) => {
		const context = await browser.newContext({ viewport: { width: 1600, height: 900 } });
		const page = await context.newPage();
		await page.route(OA_WORK_ROUTE, (route) => route.abort());

		const box = await openPaperBox(page, entityUrls);
		await expect(box.getByText(/Top paper unavailable/)).toBeVisible();
		await expect(box.getByText('Loading top paper')).toHaveCount(0);
		await context.close();
	});
});
