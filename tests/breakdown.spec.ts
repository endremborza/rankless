import { type Page } from '@playwright/test';
import { test } from './coverage/fixtures';
import * as fs from 'fs';
import { sitemapEntityUrls } from './helpers';

// Increased timeout for this test suite as it's doing a lot of exploration.
test.describe.configure({ timeout: 120000 });

const ENTITY_TYPES = ['authors', 'institutions', 'subfields'];

const optionTrees: Record<string, string[]> = {};
const semanticDescriptions: Record<string, string[]> = {};

async function explore(page: Page, url: string, level: number) {
	const selects = page.locator('.sentenceline select');
	const selectCount = await selects.count();

	if (level >= selectCount) {
		return;
	}

	const currentSelect = selects.nth(level);
	if (!(await currentSelect.isVisible())) {
		return;
	}

	const options = await currentSelect.locator('option').all();
	const optionValues = await Promise.all(options.map((o) => o.getAttribute('value')));

	for (const value of optionValues) {
		if (!value) continue;

		await currentSelect.selectOption({ value });
		await page.waitForLoadState('networkidle');

		// After selecting, collect the current state of all selects
		const allSelects = await selects.all();
		const currentPathValues = [];
		const semanticPathTexts = [];

		for (let i = 0; i <= level && i < allSelects.length; i++) {
			const selectedValue = await allSelects[i].inputValue();
			currentPathValues.push(selectedValue);

			const selectedOptionText = await allSelects[i].locator('option:checked').textContent();
			semanticPathTexts.push(selectedOptionText || '');
		}

		const key = `${url}-${level}`;
		optionTrees[key] = (optionTrees[key] || []).concat(currentPathValues.join(' > '));
		semanticDescriptions[key] = (semanticDescriptions[key] || []).concat(
			semanticPathTexts.join(' > ').replace(/\\n/g, '').replace(/\s+/g, ' ').trim()
		);

		await explore(page, url, level + 1);
	}
}

test.describe('Breakdown selection', () => {
	test('should explore all breakdown combinations', async ({ page }) => {
		for (const entityType of ENTITY_TYPES) {
			const urls = await sitemapEntityUrls(entityType, 2); // small sample to keep the test fast

			for (const url of urls) {
				await page.goto(url);
				await page.waitForSelector('.sentenceline select', { timeout: 15000 });
				await explore(page, url, 0);
			}
		}

		fs.writeFileSync('logs/breakdown-option-trees.json', JSON.stringify(optionTrees, null, 2));
		fs.writeFileSync(
			'logs/breakdown-semantic-descriptions.json',
			JSON.stringify(semanticDescriptions, null, 2)
		);
	});
});
