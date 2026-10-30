import { type Page } from '@playwright/test';
import type { TreeSpec } from '../src/lib/wire/rankless_trees/io';
import { TREE_SPECS } from '../src/lib/wire/rankless_server/responses';
import { test, expect } from './coverage/fixtures';
import {
	BREAKDOWN_SELECT,
	YEAR_SELECT,
	openFirstInstitution,
	openTree,
	settledOrder
} from './helpers';

const TOGGLE = '#impact input[aria-label="Specialization"]';

function treeRequest(param: 'year' | 'tid', value: number | string) {
	return (url: URL) =>
		url.pathname.includes('/trees/') && url.searchParams.get(param) === `${value}`;
}

async function anotherYear(page: Page): Promise<string> {
	const current = await page.locator(YEAR_SELECT).inputValue();
	return `${TREE_SPECS.yearBreaks.findLast((y) => `${y}` !== current)}`;
}

test('a failed tree fetch is shown, and retrying draws the selected year', async ({
	page,
	context
}) => {
	await openFirstInstitution(page);
	const year = await anotherYear(page);
	const isYear = treeRequest('year', year);
	await page.route(isYear, (route) => route.fulfill({ status: 500, body: 'boom' }));

	await page.locator(YEAR_SELECT).selectOption(year);
	const alert = page.locator('#impact [role=alert]');
	await expect(alert).toBeVisible();

	await page.unroute(isYear);
	const refetched = page.waitForResponse((r) => isYear(new URL(r.url())) && r.ok());
	await alert.getByRole('button', { name: 'Retry' }).click();
	await refetched;
	await expect(alert).toBeHidden();
	await expect(page).toHaveURL(new RegExp(`since=${year}`));
	const shown = await settledOrder(page);

	const direct = await context.newPage();
	await openTree(direct, page.url());
	expect(await direct.locator(YEAR_SELECT).inputValue()).toBe(year);
	expect(shown.length).toBeGreaterThan(0);
	expect(shown).toEqual(await settledOrder(direct));
});

test('a tree fetch in flight is shown as loading', async ({ page }) => {
	await openFirstInstitution(page);
	const year = await anotherYear(page);
	let release!: () => void;
	const held = new Promise<void>((resolve) => (release = resolve));
	await page.route(treeRequest('year', year), async (route) => {
		await held;
		await route.continue();
	});

	await page.locator(YEAR_SELECT).selectOption(year);
	const status = page.locator('#impact [role=status]');
	await expect(status).toBeVisible();
	release();
	await expect(status).toBeHidden();
});

test('the specialization toggle shows only on breakdowns that allow it', async ({ page }) => {
	const { institutions } = TREE_SPECS.specs;
	const key = (s: TreeSpec) => `${s.breakdowns[0].attributeType}-${s.breakdowns[0].sourceSide}`;
	const target = institutions.find(
		(t) => !t.allowSpec && institutions.every((s) => key(s) !== key(t) || !s.allowSpec)
	);
	test.skip(!target, 'no institutions first-level breakdown without specialization');
	expect(institutions[0].allowSpec, 'the opening breakdown has no toggle to hide').toBe(true);

	await openFirstInstitution(page);
	await expect(page.locator(TOGGLE)).toBeVisible();
	const select = page.locator(BREAKDOWN_SELECT).first();
	const opening = await select.inputValue();

	const landed = page.waitForResponse((r) =>
		treeRequest('tid', institutions.indexOf(target!))(new URL(r.url()))
	);
	await select.selectOption(key(target!));
	await landed;
	await expect(page.locator(TOGGLE)).toHaveCount(0);

	await select.selectOption(opening);
	await expect(page.locator(TOGGLE)).toBeVisible();
});
