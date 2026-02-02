import { test, expect } from '@playwright/test';

const sitemapRoutes = [
	'/sitemap.xml',
	'/sitemap-index.xml',
	'/sitemap-index-mini.xml',
	'/sitemap-index-entities.xml',
	'/sitemap-1.xml',
	'/sitemap-mini-1.xml',
	'/sitemap-entity-authors-1.xml'
];

for (const route of sitemapRoutes) {
	test(`sitemap route ${route} should be accessible and valid xml`, async ({ page }) => {
		const response = await page.goto(route);
		expect(response?.status()).toBe(200);
		expect(response?.headers()['content-type']).toContain('application/xml');
		const body = await response?.text();
		expect(body).toBeTruthy();
		expect(body?.startsWith('<?xml')).toBe(true);
	});
}
