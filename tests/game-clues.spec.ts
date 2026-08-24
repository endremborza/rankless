import { expect, test } from '@playwright/test';

test('game round: clues reveal, map guess scores, practice restarts', async ({ page }) => {
	await page.goto('/game-clues');
	await expect(page.locator('.clues li')).toHaveCount(1);

	await page.click('button:has-text("Next clue")');
	await expect(page.locator('.clues li')).toHaveCount(2);

	const lockButton = page.locator('.actions button.primary');
	await expect(lockButton).toBeDisabled();

	const svg = page.locator('.guess-map svg');
	const box = (await svg.boundingBox())!;
	await svg.click({ position: { x: box.width / 2, y: box.height / 3 } });
	await expect(lockButton).toBeEnabled();

	await lockButton.click();
	await expect(page.locator('.reveal h2 a')).toHaveAttribute('href', /\/institutions\//);
	await expect(page.locator('.verdict')).toContainText('points');
	await expect(page.locator('.distance-label')).toContainText('km');

	await page.click('button:has-text("Play a practice round")');
	await expect(page.locator('.mode-label')).toHaveText('Practice round');
	await expect(page.locator('.clues li')).toHaveCount(1);
});
