import { type Page } from '@playwright/test';
import { expect, test } from './coverage/fixtures';

// The browse table: cohort-wide sort and filter go through the server, page-local columns cost one
// metric-values call per page and never reorder the cohort.

test.describe.configure({ timeout: 120_000 });

async function ranks(page: Page): Promise<number[]> {
	return page.$$eval('tbody td.col-rank', (tds) =>
		tds.map((td) => parseInt((td.textContent ?? '').replace(/,/g, '')))
	);
}

async function column(page: Page, header: string): Promise<number[]> {
	const idx = await page.$$eval(
		'thead tr:last-child th',
		(ths, h) => ths.findIndex((th) => (th.textContent ?? '').trim().startsWith(h)),
		header
	);
	expect(idx, `column ${header}`).toBeGreaterThan(-1);
	return page.$$eval(
		`tbody tr td:nth-child(${idx + 1})`,
		(tds) => tds.map((td) => parseFloat((td.textContent ?? '').replace(/[,%]/g, ''))),
		undefined
	);
}

function nonIncreasing(v: number[]) {
	return v.every((x, i) => i === 0 || x <= v[i - 1]);
}

// Competition ranks: never past the row's position, never decreasing, ties share a rank.
function ranksValid(r: number[]) {
	return r.every((x, i) => x >= 1 && x <= i + 1 && (i === 0 || x >= r[i - 1]));
}

test('sorts the whole cohort by a global metric and pages past the first 100', async ({ page }) => {
	await page.goto('/institutions/table');
	await page.waitForSelector('tbody tr');
	let r = await ranks(page);
	expect(r.length).toBe(100);
	expect(r[0]).toBe(1);
	expect(ranksValid(r)).toBeTruthy();
	expect(nonIncreasing(await column(page, 'Citations'))).toBeTruthy();

	await page.locator('thead th', { hasText: 'Impact score' }).click();
	await page.waitForURL(/sort=impact_score/);
	await page.waitForSelector('tbody tr');
	r = await ranks(page);
	expect(r.length).toBe(100);
	expect(ranksValid(r)).toBeTruthy();
	expect(nonIncreasing(await column(page, 'Impact score'))).toBeTruthy();

	await page.getByRole('button', { name: /Load more/ }).click();
	await page.waitForFunction(() => document.querySelectorAll('tbody tr').length >= 200);
	r = await ranks(page);
	expect(r.length).toBe(200);
	expect(r[100]).toBeGreaterThanOrEqual(100);
	expect(ranksValid(r)).toBeTruthy();
	expect(nonIncreasing(await column(page, 'Impact score'))).toBeTruthy();

	// A sort change after paging re-seeds the page: no rows of the previous ordering linger.
	await page.locator('thead th', { hasText: 'Papers' }).click();
	await page.waitForURL(/sort=papers/);
	await page.waitForFunction(() => document.querySelectorAll('tbody tr').length === 100);
	r = await ranks(page);
	expect(r[0]).toBe(1);
	expect(ranksValid(r)).toBeTruthy();
	expect(nonIncreasing(await column(page, 'Papers'))).toBeTruthy();
});

test('narrows the cohort to a field with score and standing columns', async ({ page }) => {
	await page.goto('/institutions/table');
	const select = page.getByLabel('Narrow to a field');
	const first = await select.locator('option').nth(1).getAttribute('value');
	await select.selectOption(first!);
	await page.waitForURL(/subfield=/);
	await page.waitForSelector('tbody tr');
	await expect(page.locator('thead th', { hasText: 'Field score' })).toBeVisible();
	await expect(page.locator('thead th', { hasText: 'Standing' })).toBeVisible();
	expect(nonIncreasing(await column(page, 'Citations'))).toBeTruthy();
	expect((await column(page, 'Field citations')).every((v) => v > 0)).toBeTruthy();
});

test('name search returns matches with their cohort rank', async ({ page }) => {
	await page.goto('/institutions/table');
	const name = (await page.locator('tbody td.col-name a').nth(5).textContent())!.trim();
	await page.getByLabel('Search by name').fill(name.split(' ')[0]);
	await page.getByLabel('Search by name').press('Enter');
	await page.waitForURL(/q=/);
	await page.waitForSelector('tbody tr');
	const r = await ranks(page);
	expect(r.length).toBeGreaterThan(0);
	expect(r.length).toBeLessThan(100);
	expect(r).toEqual([...r].sort((a, b) => a - b));
});

test('a page-local column costs one call and never reorders the cohort', async ({ page }) => {
	const metricCalls: string[] = [];
	page.on('request', (req) => {
		if (/\/v1\/metrics\/institutions\?/.test(req.url())) metricCalls.push(req.url());
	});
	await page.goto('/institutions/table');
	await page.waitForSelector('tbody tr');
	const before = await ranks(page);

	await page.getByLabel('Add a page-local column').selectOption('window_papers');
	await page.getByRole('button', { name: 'Add', exact: true }).click();
	await page.waitForSelector('th.sortable.local');
	await expect(page.locator('th.group.local')).toContainText('loaded rows');
	await page.waitForFunction(
		() => !Array.from(document.querySelectorAll('td.local')).some((td) => td.textContent === '–')
	);
	expect(metricCalls.length).toBe(1);
	expect(new URL(metricCalls[0]).searchParams.get('ids')!.split(',').length).toBe(100);
	expect(await ranks(page)).toEqual(before);

	await page.locator('th.sortable.local').click();
	expect(nonIncreasing(await column(page, 'Papers 20'))).toBeTruthy();
	expect([...(await ranks(page))].sort((a, b) => a - b)).toEqual(before);
});
