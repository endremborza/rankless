import { test, expect } from '@playwright/test';

const NAV_LABELS = ['authors', 'institutions', 'journals', 'countries', 'fields'];

test.describe('Header search', () => {
	test('clicking nav link opens search with input visible and focused', async ({ page }) => {
		await page.goto('/');
		await page.waitForSelector('#site-header', { timeout: 10000 });

		const navButton = page.locator('.nav-link', { hasText: 'authors' });
		await navButton.click();

		const input = page.locator('#search-input');
		await expect(input).toBeVisible({ timeout: 3000 });
		await expect(input).toBeFocused();
	});

	test('header and search bar stay above search overlay', async ({ page }) => {
		await page.goto('/');
		await page.waitForSelector('#site-header', { timeout: 10000 });

		await page.locator('.nav-link', { hasText: 'authors' }).click();
		await page.waitForSelector('#search-input', { timeout: 3000 });

		const headerBox = await page.locator('#site-header').boundingBox();
		const searchBarBox = await page.locator('#search-bar').boundingBox();
		expect(headerBox).toBeTruthy();
		expect(searchBarBox).toBeTruthy();

		const headerZ = await page
			.locator('#site-header')
			.evaluate((el) => getComputedStyle(el).zIndex);
		const searchBarZ = await page
			.locator('#search-bar')
			.evaluate((el) => getComputedStyle(el).zIndex);
		const overlayZ = await page
			.locator('.search-results')
			.evaluate((el) => getComputedStyle(el).zIndex);

		expect(Number(headerZ)).toBeGreaterThan(Number(overlayZ));
		expect(Number(searchBarZ)).toBeGreaterThan(Number(overlayZ));
	});

	test('other nav links remain clickable while search is open', async ({ page }) => {
		await page.goto('/');
		await page.waitForSelector('#site-header', { timeout: 10000 });

		await page.locator('.nav-link', { hasText: 'authors' }).click();
		await expect(page.locator('#search-input')).toBeVisible({ timeout: 3000 });

		const journalsButton = page.locator('.nav-link', { hasText: 'journals' });
		await expect(journalsButton).toBeVisible();
		await journalsButton.click();

		const input = page.locator('#search-input');
		await expect(input).toBeVisible();
		await expect(input).toBeFocused();

		const activeButton = page.locator('.nav-link.active', { hasText: 'journals' });
		await expect(activeButton).toBeVisible();
	});

	test('wide viewport shows all nav links', async ({ browser }) => {
		const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
		const page = await context.newPage();
		await page.goto('/');
		await page.waitForSelector('#site-header', { timeout: 10000 });

		for (const label of NAV_LABELS) {
			await expect(page.locator('.nav-link', { hasText: label })).toBeVisible();
		}
		await context.close();
	});

	test('narrow viewport collapses nav into dropdown', async ({ browser }) => {
		const context = await browser.newContext({ viewport: { width: 500, height: 667 } });
		const page = await context.newPage();
		await page.goto('/');
		await page.waitForSelector('#site-header', { timeout: 10000 });

		const dropdownTrigger = page.locator('.dropdown-trigger');
		await expect(dropdownTrigger).toBeVisible();
		await dropdownTrigger.click();

		const dropdownMenu = page.locator('.dropdown-menu');
		await expect(dropdownMenu).toBeVisible({ timeout: 2000 });

		const firstItem = dropdownMenu.locator('.dropdown-item').first();
		await firstItem.click();

		await expect(page.locator('#search-input')).toBeVisible({ timeout: 3000 });
		await expect(page.locator('#search-input')).toBeFocused();
		await context.close();
	});

	test('escape closes search', async ({ page }) => {
		await page.goto('/');
		await page.waitForSelector('#site-header', { timeout: 10000 });

		await page.locator('.nav-link', { hasText: 'authors' }).click();
		await expect(page.locator('#search-input')).toBeVisible({ timeout: 3000 });

		await page.keyboard.press('Escape');
		await expect(page.locator('#search-input')).not.toBeVisible({ timeout: 2000 });
	});
});
