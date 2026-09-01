import { expect, test } from '@playwright/test';

import { LIVES, PATH } from '../src/lib/utils/game-countries';

// Fixture country cards (tests/seed-game.ts) all resolve to Hungary, so the
// spec can answer correctly or miss on purpose without knowing the deck order.
const CORRECT = 'Hungary';
// How many cards tests/seed-game.ts seeds — one more than a full run spends,
// so the run ends on lives rather than on the deck.
const DECK = LIVES + 2;

async function miss(page: import('@playwright/test').Page) {
	await page.locator('.option', { hasNotText: CORRECT }).first().click();
}

test('campusquest run: every answer holds its reveal, a miss costs a life, the last one ends the run', async ({
	page
}) => {
	await page.goto(PATH);
	await page.click('button:has-text("Play today\'s run")');

	await expect(page.locator('.option')).toHaveCount(4);
	await expect(page.locator('.timer')).toBeVisible();
	await expect(page.locator('.badge').first()).toBeVisible();
	await expect(page.locator('.progress-row')).toContainText(`1/${DECK}`);
	await expect(page.locator('.lives')).toHaveAttribute(
		'aria-label',
		`${LIVES} of ${LIVES} lives left`
	);

	// A hit holds the same reveal a miss does, under a green verdict.
	await page.click(`.option:has-text("${CORRECT}")`);
	await expect(page.locator('.reveal .verdict-tag')).toHaveText(/Correct/);
	await expect(page.locator('.reveal')).toContainText('Fixture note');
	await page.click('button:has-text("Next")');
	await expect(page.locator('.progress-row')).toContainText(`2/${DECK}`);

	// Deliberate misses: the run survives all but the last one.
	for (let spent = 1; spent < LIVES; spent++) {
		await miss(page);
		await expect(page.locator('.reveal .verdict-tag')).toHaveText(/Wrong/);
		await expect(page.locator('.reveal')).toContainText(CORRECT);
		await expect(page.locator('.lives')).toHaveAttribute(
			'aria-label',
			`${LIVES - spent} of ${LIVES} lives left`
		);
		await page.click('button:has-text("Next")');
		await expect(page.locator('.timer')).toBeVisible();
	}

	// The last miss still holds the reveal; the result screen sits behind it.
	await miss(page);
	await expect(page.locator('.reveal')).toContainText('Fixture note');
	await expect(page.locator('button:has-text("Next")')).toHaveCount(0);
	await expect(page.locator('.option.correct')).toHaveCount(1);
	await expect(page.locator('.option.wrong')).toHaveCount(1);
	await page.click('button:has-text("See result")');

	// Result: verdict, score, the misses with their true country, the day's
	// standing from the run log, and the stats sheet over the daily history.
	await expect(page.locator('.verdict')).toHaveText(`Run over at card ${LIVES + 1} of ${DECK}`);
	await expect(page.locator('.score-big')).toHaveText('1');
	await expect(page.locator('.misses li')).toHaveCount(LIVES);
	await expect(page.locator('.misses .miss-where').first()).toContainText(CORRECT);
	await expect(page.locator('.standing')).toHaveText(/#\d+ of \d+ today/);
	await page.click('.stats-line');
	await expect(page.locator('.sheet .tile').first()).toContainText('1');

	// The finished daily survives a reload, misses resolved against the same deck.
	await page.reload();
	await expect(page.locator('.score-big')).toHaveText('1');
	await expect(page.locator('.misses li')).toHaveCount(LIVES);

	await page.click('button:has-text("Practice run")');
	await expect(page.locator('.mode-label')).toHaveText('Practice run');
	await expect(page.locator('.option')).toHaveCount(4);
});
