import { expect, test } from '@playwright/test';

import { DAILY_RECIPE, DAILY_SIZE, LIVES, PATH } from '../src/lib/utils/game-geo';

// Every fixture card's answer is knowable from its option text
// (tests/seed-game.ts), whatever the deck and option order.
const ANSWER = /Hungary|Budapest|Near One|Fixture Intruder|Fixture Local/;

async function answer(page: import('@playwright/test').Page, correctly: boolean) {
	const options = page.locator('.option:not([disabled])');
	await (correctly ? options.filter({ hasText: ANSWER }) : options.filter({ hasNotText: ANSWER }))
		.first()
		.click();
}

test('campusquest daily: ten cards of the recipe, a lifeline for half a point, a miss, the grid', async ({
	page
}) => {
	await page.goto(PATH);
	await page.click('button:has-text("Play today\'s run")');

	await expect(page.locator('.option')).toHaveCount(4);
	await expect(page.locator('.timer')).toBeVisible();
	await expect(page.locator('.badge').first()).toBeVisible();
	await expect(page.locator('.progress-row')).toContainText(`1/${DAILY_SIZE}`);

	// Card 1: a plain hit holds its reveal under a green verdict.
	await answer(page, true);
	await expect(page.locator('.reveal .verdict-tag')).toHaveText('✓ Correct');
	await expect(page.locator('.reveal')).toContainText('Fixture note');
	await page.click('button:has-text("Next")');
	await expect(page.locator('.progress-row')).toContainText(`2/${DAILY_SIZE}`);

	// Card 2: the 50:50 leaves two options and the hit is worth half.
	await page.click('.lifeline');
	await expect(page.locator('.option:not([disabled])')).toHaveCount(2);
	await expect(page.locator('.option.faded')).toHaveCount(2);
	await answer(page, true);
	await expect(page.locator('.reveal .verdict-tag')).toHaveText('✓ Correct · ½');
	await page.click('button:has-text("Next")');
	await expect(page.locator('.progress-row')).toContainText('1½');

	// Card 3: a miss shows the answer and costs no life — the run goes on.
	await answer(page, false);
	await expect(page.locator('.reveal .verdict-tag')).toHaveText('✗ Wrong');
	await expect(page.locator('.option.correct')).toHaveCount(1);
	await expect(page.locator('.option.wrong')).toHaveCount(1);
	await page.click('button:has-text("Next")');

	// The rest of the recipe, every kind of card, all placed; the nearest
	// reveal shows the map.
	for (let i = 3; i < DAILY_SIZE; i++) {
		await expect(page.locator('.progress-row')).toContainText(`${i + 1}/${DAILY_SIZE}`);
		await answer(page, true);
		await expect(page.locator('.reveal .verdict-tag')).toHaveText('✓ Correct');
		if (DAILY_RECIPE[i] === 'nearest-card') {
			await expect(page.locator('.reveal svg')).toBeVisible();
			await expect(page.locator('.opt-km')).toHaveCount(4);
		}
		if (DAILY_RECIPE[i] === 'intruder-card') {
			await expect(page.locator('.stage .stress')).toHaveText('not');
			await expect(page.locator('.reveal .sheet-sub')).toHaveText('Budapest, Hungary');
		}
		await page.click(`button:has-text("${i === DAILY_SIZE - 1 ? 'See result' : 'Next'}")`);
	}

	// Result: 8 hits + one half = 8½, the grid, the miss with its answer, the
	// day's standing from the run log, and the stats sheet.
	await expect(page.locator('.verdict')).toHaveText(`8½ of ${DAILY_SIZE} placed`);
	await expect(page.locator('.score-big')).toHaveText('8½');
	await expect(page.locator('.grid')).toHaveText('🟩🟨🟥' + '🟩'.repeat(DAILY_SIZE - 3));
	await expect(page.locator('.misses li')).toHaveCount(1);
	await expect(page.locator('.misses .miss-where')).toHaveText(ANSWER);
	await expect(page.locator('.standing')).toHaveText(/#\d+ of \d+ today/);
	await expect(page.locator('.share-preview')).toContainText(`8½/${DAILY_SIZE}`);
	await page.click('.stats-line');
	await expect(page.locator('.sheet .tile').first()).toContainText('1');

	// The finished daily survives a reload, ids resolved against the same deck.
	await page.reload();
	await expect(page.locator('.score-big')).toHaveText('8½');
	await expect(page.locator('.grid')).toHaveText('🟩🟨🟥' + '🟩'.repeat(DAILY_SIZE - 3));

	// Survival: lives, no lifeline, the whole pack.
	await page.click('button:has-text("Survival")');
	await expect(page.locator('.mode-label')).toHaveText('Survival');
	await expect(page.locator('.option')).toHaveCount(4);
	await expect(page.locator('.lifeline')).toHaveCount(0);
	await expect(page.locator('.lives')).toHaveAttribute(
		'aria-label',
		`${LIVES} of ${LIVES} lives left`
	);
	await answer(page, false);
	await page.click('button:has-text("Next")');
	await expect(page.locator('.lives')).toHaveAttribute(
		'aria-label',
		`${LIVES - 1} of ${LIVES} lives left`
	);
});
