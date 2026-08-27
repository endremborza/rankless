import { expect, test } from '@playwright/test';

// Fixture country cards (tests/seed-game.ts) all resolve to Hungary, so the
// spec can answer correctly or miss on purpose without knowing the shuffled
// deck order.
const CORRECT = 'Hungary';
const LIVES = 3;

async function miss(page: import('@playwright/test').Page) {
	await page.locator('.option', { hasNotText: CORRECT }).first().click();
}

test('country run: a miss costs a life, the run ends when the last one goes', async ({ page }) => {
	await page.goto('/game-countries');
	await page.click('button:has-text("Start today\'s run")');

	await expect(page.locator('.option')).toHaveCount(4);
	await expect(page.locator('.timer')).toBeVisible();
	await expect(page.locator('.progress-row')).toContainText('1/5');
	await expect(page.locator('.lives')).toHaveAttribute(
		'aria-label',
		`${LIVES} of ${LIVES} lives left`
	);

	await page.click(`.option:has-text("${CORRECT}")`);
	await expect(page.locator('.progress-row')).toContainText('score 1');
	await expect(page.locator('.progress-row')).toContainText('2/5');

	// Deliberate misses: the run survives all but the last one.
	for (let spent = 1; spent < LIVES; spent++) {
		await miss(page);
		await expect(page.locator('.reveal')).toContainText(CORRECT);
		await expect(page.locator('.reveal')).toContainText('Fixture note');
		await expect(page.locator('.lives')).toHaveAttribute(
			'aria-label',
			`${LIVES - spent} of ${LIVES} lives left`
		);
		await page.click('button:has-text("Keep going")');
		await expect(page.locator('.timer')).toBeVisible();
	}

	await miss(page);
	await expect(page.locator('.verdict')).toContainText('1');
	await expect(page.locator('button:has-text("Keep going")')).toHaveCount(0);
	await expect(page.locator('.option.correct')).toHaveCount(1);
	await expect(page.locator('.option.wrong')).toHaveCount(1);

	await page.click('button:has-text("Practice run")');
	await expect(page.locator('.mode-label')).toHaveText('Practice run');
	await expect(page.locator('.option')).toHaveCount(4);
});
