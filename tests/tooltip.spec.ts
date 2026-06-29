import { test, expect } from './coverage/fixtures';
import { sitemapEntityUrls } from './helpers';

// The InfoTip ("what is this?") tooltips flip above their trigger by default. The sticky #site-header
// occludes the top of the viewport, so a near-top trigger (the "indexed" link in the hero stat line)
// must drop its tooltip *below* instead of into the header band, where it would be painted over.
test('InfoTip clears the sticky header instead of hiding behind it', async ({ browser }) => {
	const [url] = await sitemapEntityUrls('authors', 1);
	test.skip(!url, 'no author sitemap entries');

	const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
	const page = await context.newPage();
	await page.goto(url, { waitUntil: 'load' });
	await page.waitForSelector('#overview h1', { timeout: 20_000 });

	const trigger = page.locator('.info-trigger.inline').first();
	await trigger.scrollIntoViewIfNeeded();

	const headerBottom = await page.evaluate(
		() => document.querySelector('#site-header')!.getBoundingClientRect().bottom
	);
	// Park the trigger just below the header so an above-placed tooltip *would* intrude into it.
	const box = (await trigger.boundingBox())!;
	await page.evaluate((dy) => window.scrollBy(0, dy), box.y - (headerBottom + 12));
	await page.waitForTimeout(50);

	await trigger.hover();
	await page.waitForTimeout(120);

	const tip = (await page.locator('.info-tip').boundingBox())!;
	expect(tip, 'tooltip did not render on hover').toBeTruthy();
	expect(tip.y, 'tooltip top intrudes into the sticky header band').toBeGreaterThanOrEqual(
		headerBottom - 1
	);

	await context.close();
});
