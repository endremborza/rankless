import { test, expect } from './coverage/fixtures';
import { sitemapEntityUrls } from './helpers';

test.describe('Infobox layout', () => {
	let entityUrl: string;

	test.beforeAll(async () => {
		[entityUrl] = await sitemapEntityUrls('authors', 1);
	});

	test('narrow viewport: infobox is visible with reasonable height', async ({ browser }) => {
		const context = await browser.newContext({ viewport: { width: 375, height: 667 } });
		const page = await context.newPage();
		await page.goto(entityUrl);
		await page.waitForSelector('.infobox-container', { timeout: 15000 });

		const box = await page.locator('.infobox-container').first().boundingBox();
		expect(box).toBeTruthy();
		expect(box!.height).toBeGreaterThan(80);
		expect(box!.width).toBeGreaterThan(300);
		await context.close();
	});

	test('wide viewport: infobox appears left of figure', async ({ browser }) => {
		const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
		const page = await context.newPage();
		await page.goto(entityUrl);
		await page.waitForSelector('.infobox-container', { timeout: 15000 });

		const infoBox = await page.locator('.infobox-container').first().boundingBox();
		const figureBox = await page.locator('.figure-container').first().boundingBox();
		expect(infoBox).toBeTruthy();
		expect(figureBox).toBeTruthy();
		expect(infoBox!.x).toBeLessThan(figureBox!.x);
		await context.close();
	});

	test('narrow viewport: pli-basics text does not overflow', async ({ browser }) => {
		const context = await browser.newContext({ viewport: { width: 375, height: 667 } });
		const page = await context.newPage();
		await page.goto(entityUrl);
		await page.waitForSelector('.plibox-container', { timeout: 15000 });

		const containerBox = await page.locator('.infobox-container').first().boundingBox();
		const pliBox = await page.locator('.plibox-container').first().boundingBox();
		expect(containerBox).toBeTruthy();
		expect(pliBox).toBeTruthy();
		expect(pliBox!.width).toBeLessThanOrEqual(containerBox!.width + 1);
		await context.close();
	});
});
