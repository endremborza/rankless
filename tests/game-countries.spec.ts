import { expect, test } from '@playwright/test';

// Fixture country cards (tests/seed-game.ts) all resolve to Hungary, so the
// spec can answer correctly or miss on purpose without knowing the shuffled
// deck order.
const CORRECT = 'Hungary';

test('country run: correct picks advance, a wrong pick ends the run with the score', async ({
	page
}) => {
	await page.goto('/game-countries');
	await page.click('button:has-text("Start today\'s run")');

	await expect(page.locator('.option')).toHaveCount(4);
	await expect(page.locator('.timer')).toBeVisible();
	await expect(page.locator('.progress-row')).toContainText('1/3');

	await page.click(`.option:has-text("${CORRECT}")`);
	await expect(page.locator('.progress-row')).toContainText('score 1');
	await expect(page.locator('.progress-row')).toContainText('2/3');

	// Deliberate miss: any option that is not the correct country.
	await page.locator('.option', { hasNotText: CORRECT }).first().click();
	await expect(page.locator('.reveal')).toContainText(CORRECT);
	await expect(page.locator('.reveal')).toContainText('Fixture note');
	await expect(page.locator('.verdict')).toContainText('1');
	await expect(page.locator('.option.correct')).toHaveCount(1);
	await expect(page.locator('.option.wrong')).toHaveCount(1);

	await page.click('button:has-text("Practice run")');
	await expect(page.locator('.mode-label')).toHaveText('Practice run');
	await expect(page.locator('.option')).toHaveCount(4);
});
