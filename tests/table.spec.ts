import { type Page } from '@playwright/test';
import { expect, test } from './coverage/fixtures';

// The browse table: the ranking call and the `where` expression go through the server, a header
// click reorders the loaded rows only, page-local columns cost one metric-values call per page.

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

async function total(page: Page): Promise<number> {
	const note = (await page.locator('.cohort-note').textContent()) ?? '';
	return parseInt(note.match(/of ([\d,]+)/)![1].replace(/,/g, ''));
}

// One clause through the builder: metric, an optional field argument, operator, operand.
async function narrow(
	page: Page,
	metric: string,
	op: string,
	value: string | { label: string },
	field?: string
) {
	// The ranking picker may show a field of its own, so the builder's controls are scoped.
	const block = page.locator('section.block', { hasText: 'Filter' });
	await block.getByLabel('Narrow by a metric').selectOption(metric);
	if (field) await block.getByLabel('Field', { exact: true }).selectOption(field);
	await block.getByLabel('Operator').selectOption(op);
	const input = block.getByLabel('Value', { exact: true });
	if (typeof value === 'string') await input.fill(value);
	else await input.selectOption(value);
	await page.getByRole('button', { name: 'Narrow', exact: true }).click();
}

function nonIncreasing(v: number[]) {
	return v.every((x, i) => i === 0 || x <= v[i - 1]);
}

function nonDecreasing(v: number[]) {
	return v.every((x, i) => i === 0 || x >= v[i - 1]);
}

// Competition ranks: never past the row's position, never decreasing, ties share a rank.
function ranksValid(r: number[]) {
	return r.every((x, i) => x >= 1 && x <= i + 1 && (i === 0 || x >= r[i - 1]));
}

const sorted = (r: number[]) => [...r].sort((a, b) => a - b);

test('ranks the whole cohort from the picker and pages past the first 100', async ({ page }) => {
	await page.goto('/institutions/table');
	await page.waitForSelector('tbody tr');
	let r = await ranks(page);
	expect(r.length).toBe(100);
	expect(r[0]).toBe(1);
	expect(ranksValid(r)).toBeTruthy();
	expect(nonIncreasing(await column(page, 'Citations'))).toBeTruthy();

	await page.getByLabel('Rank', { exact: true }).selectOption('impact_score');
	await page.waitForURL(/sort=impact_score/);
	await page.waitForSelector('tbody tr');
	r = await ranks(page);
	expect(r.length).toBe(100);
	expect(ranksValid(r)).toBeTruthy();
	expect(nonIncreasing(await column(page, 'Impact score'))).toBeTruthy();
	await expect(page.locator('th.ranked')).toContainText('Impact score');

	await page.getByRole('button', { name: /Load more/ }).click();
	await page.waitForFunction(() => document.querySelectorAll('tbody tr').length >= 200);
	r = await ranks(page);
	expect(r.length).toBe(200);
	expect(r[100]).toBeGreaterThanOrEqual(100);
	expect(ranksValid(r)).toBeTruthy();
	expect(nonIncreasing(await column(page, 'Impact score'))).toBeTruthy();

	// A ranking change after paging re-seeds the page: no rows of the previous ordering linger.
	await page.getByLabel('Rank', { exact: true }).selectOption('papers');
	await page.waitForURL(/sort=papers/);
	await page.waitForFunction(() => document.querySelectorAll('tbody tr').length === 100);
	r = await ranks(page);
	expect(r[0]).toBe(1);
	expect(ranksValid(r)).toBeTruthy();
	expect(nonIncreasing(await column(page, 'Papers'))).toBeTruthy();
});

test('a header click sorts the loaded rows only and leaves the ranking alone', async ({ page }) => {
	await page.goto('/institutions/table');
	await page.waitForSelector('tbody tr');
	const before = await ranks(page);
	await page.locator('thead th', { hasText: 'Papers' }).click();
	expect(nonIncreasing(await column(page, 'Papers'))).toBeTruthy();
	expect(sorted(await ranks(page))).toEqual(before);
	expect(page.url()).not.toMatch(/sort=/);
	await expect(page.locator('th.ranked')).toContainText('Citations');
	await page.locator('thead th', { hasText: 'Papers' }).click();
	expect(nonDecreasing(await column(page, 'Papers'))).toBeTruthy();
	expect(sorted(await ranks(page))).toEqual(before);
});

test('a field ranking brings its family of columns and the standing', async ({ page }) => {
	await page.goto('/institutions/table');
	await page.waitForSelector('tbody tr');
	await page.getByLabel('Rank', { exact: true }).selectOption('field_score');
	const field = page.getByLabel('Field', { exact: true });
	const names = (await field.locator('option').allTextContents()).slice(1).map((s) => s.trim());
	expect(names).toEqual([...names].sort((a, b) => a.localeCompare(b)));
	const option = field.locator('option').nth(1);
	const fieldName = (await option.textContent())!.trim();
	const fieldId = (await option.getAttribute('value'))!;
	await field.selectOption(fieldId);
	await page.getByRole('button', { name: 'Rank', exact: true }).click();
	await page.waitForURL(/sort=field_score/);
	await page.waitForSelector('tbody tr');
	await expect(page.locator('th.ranked')).toContainText(`${fieldName} score`);
	await expect(page.locator('thead th', { hasText: `${fieldName} share` })).toBeVisible();
	await expect(page.locator('thead th', { hasText: 'Standing' })).toBeVisible();
	expect(nonIncreasing(await column(page, `${fieldName} score`))).toBeTruthy();
	const shares = await column(page, `${fieldName} share`);
	expect(shares.every((v) => v >= 0 && v <= 100)).toBeTruthy();
	expect(ranksValid(await ranks(page))).toBeTruthy();

	// Active in the field: a clause on the field's citations, argument and all.
	const all = await total(page);
	await narrow(page, 'field_citations', 'gt', '0', fieldId);
	await page.waitForURL(/where=/);
	await page.waitForSelector('tbody tr');
	await expect(page.locator('.chip', { hasText: `${fieldName} citations > 0` })).toBeVisible();
	expect(await total(page)).toBeLessThanOrEqual(all);
	expect((await column(page, `${fieldName} citations`)).every((v) => v > 0)).toBeTruthy();
});

test('narrows the cohort by a country and by a numeric clause', async ({ page }) => {
	await page.goto('/institutions/table');
	await page.waitForSelector('tbody tr');
	const all = await total(page);
	await narrow(page, 'country', 'eq', { label: 'Hungary' });
	await page.waitForURL(/where=country/);
	await page.waitForSelector('tbody tr');
	await expect(page.locator('.chip', { hasText: 'Country = Hungary' })).toBeVisible();
	await expect(page.locator('.cohort-note')).toContainText('where country = hun');
	const inCountry = await total(page);
	expect(inCountry).toBeLessThan(all);
	expect((await ranks(page))[0]).toBe(1);

	await page.getByRole('button', { name: 'Drop Country = Hungary' }).click();
	await page.waitForURL((u) => !u.searchParams.has('where'));
	await page.waitForSelector('tbody tr');
	await narrow(page, 'country', 'ne', { label: 'Hungary' });
	await page.waitForURL(/where=country/);
	await page.waitForSelector('tbody tr');
	await expect(page.locator('.chip', { hasText: 'Country ≠ Hungary' })).toBeVisible();
	expect(await total(page)).toBe(all - inCountry);

	const papers = await column(page, 'Papers');
	const floor = papers[50];
	await narrow(page, 'papers', 'ge', String(floor));
	await page.waitForURL(/papers/);
	await page.waitForSelector('tbody tr');
	await expect(
		page.locator('.chip', { hasText: `Papers ≥ ${floor.toLocaleString()}` })
	).toBeVisible();
	expect((await column(page, 'Papers')).every((v) => v >= floor)).toBeTruthy();
	expect(ranksValid(await ranks(page))).toBeTruthy();
	expect(await total(page)).toBeLessThan(all - inCountry);
});

test('an expression the chips cannot show is edited as text, a bad one is refused', async ({
	page
}) => {
	await page.goto(
		'/institutions/table?where=country%3Dhun%20and%20not%20(city%3Dbudapest%20or%20papers%3C10)'
	);
	await page.waitForSelector('tbody tr');
	const box = page.getByLabel('Narrowing expression');
	await expect(box).toHaveValue('country=hun and not (city=budapest or papers<10)');
	await expect(page.locator('.chip')).toHaveCount(0);
	expect(await total(page)).toBeGreaterThan(0);
	await box.fill('country = hun and papers >');
	await page.getByRole('button', { name: 'Apply', exact: true }).click();
	await page.waitForURL(/papers\+%3E/);
	await expect(page.locator('.error')).toContainText('expected a value');
});

test('ranks authors by a field score', async ({ page }) => {
	await page.goto('/authors/table');
	await page.waitForSelector('tbody tr');
	await page.getByLabel('Rank', { exact: true }).selectOption('field_score');
	const field = page.getByLabel('Field', { exact: true });
	const option = field.locator('option').nth(1);
	const fieldName = (await option.textContent())!.trim();
	await field.selectOption((await option.getAttribute('value'))!);
	await page.getByRole('button', { name: 'Rank', exact: true }).click();
	await page.waitForURL(/sort=field_score/);
	await page.waitForSelector('tbody tr');
	expect(nonIncreasing(await column(page, `${fieldName} score`))).toBeTruthy();
	const r = await ranks(page);
	expect(r[0]).toBe(1);
	expect(ranksValid(r)).toBeTruthy();
	// On a root too large to scan the ranking is screened, and both the note and the header say so.
	const note = (await page.locator('.cohort-note').textContent()) ?? '';
	if (note.includes('among the top')) {
		await expect(page.locator('th.group').first()).toContainText('top 1,000');
	}
});

test('a pinned entity stays on the table through every ranking', async ({ page }) => {
	await page.goto('/institutions/table');
	await page.waitForSelector('tbody tr');
	const name = (await page.locator('tbody td.col-name a').nth(30).textContent())!.trim();
	await page.getByPlaceholder(/^Pin /).fill(name);
	await page.locator('.ps-results button').first().click();
	await page.waitForURL(/pin=/);
	const pinned = page.locator('tbody tr.pinned');
	await expect(pinned).toHaveCount(1);
	const rank = parseInt((await pinned.locator('td.col-rank').textContent())!.replace(/,/g, ''));
	expect(rank).toBeGreaterThan(1);
	// The pinned row is not repeated in the ranked list.
	expect((await ranks(page)).filter((r) => r === rank).length).toBe(1);

	await page.getByLabel('Rank', { exact: true }).selectOption('impact_score');
	await page.waitForURL(/sort=impact_score/);
	expect(page.url()).toMatch(/pin=/);
	await expect(page.locator('tbody tr.pinned')).toHaveCount(1);

	await page.getByRole('button', { name: /^Unpin / }).click();
	await page.waitForURL((u) => !u.searchParams.has('pin'));
	await expect(page.locator('tbody tr.pinned')).toHaveCount(0);
});

test('a page-local column costs one call, shows its cells pending and never reorders the cohort', async ({
	page
}) => {
	const metricCalls: string[] = [];
	await page.route(/\/v1\/metrics\/institutions\?/, async (route) => {
		metricCalls.push(route.request().url());
		await new Promise((r) => setTimeout(r, 1200));
		await route.continue();
	});
	await page.goto('/institutions/table');
	await page.waitForSelector('tbody tr');
	const before = await ranks(page);

	await page.getByLabel('Add', { exact: true }).selectOption('window_papers');
	await page.getByRole('button', { name: 'Add', exact: true }).click();
	await page.waitForSelector('th.sortable.local');
	await expect(page.locator('th.group.local')).toContainText('loaded rows');
	await expect(page.locator('td.local.pending').first()).toHaveText('…');
	await page.waitForFunction(() => document.querySelectorAll('td.local.pending').length === 0);
	expect(
		await page.$$eval('td.local', (tds) => tds.every((td) => td.textContent!.trim() !== '…'))
	).toBeTruthy();
	expect(metricCalls.length).toBe(1);
	const u = new URL(metricCalls[0]);
	expect(u.searchParams.get('ids')!.split(',').length).toBe(100);
	expect(u.searchParams.get('metrics')).toMatch(/^window_papers\(\d{4}, \d{4}\)$/);
	expect(await ranks(page)).toEqual(before);

	await page.locator('th.sortable.local').click();
	expect(nonIncreasing(await column(page, 'Papers 20'))).toBeTruthy();
	expect(sorted(await ranks(page))).toEqual(before);
});
