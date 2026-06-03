import { test as base, expect } from '@playwright/test';
import { coverageOptions } from './options';

// COVERAGE is set by the `test:e2e:cov` script. When unset this fixture is a
// no-op, so the same specs run unchanged under the default playwright.config.ts.
const COLLECT = !!process.env.COVERAGE;

export const test = base.extend<{ collectCoverage: void }>({
	collectCoverage: [
		async ({ page, browserName }, use) => {
			// page.coverage is Chromium-only.
			const active = COLLECT && browserName === 'chromium';
			if (active) {
				await page.coverage.startJSCoverage({ resetOnNavigation: false });
			}

			await use();

			if (active) {
				const entries = await page.coverage.stopJSCoverage();
				// Pages that ran no app script (e.g. XML sitemap routes) yield [];
				// monocart rejects an empty add.
				if (entries.length) {
					const { CoverageReport } = await import('monocart-coverage-reports');
					await new CoverageReport(coverageOptions).add(entries);
				}
			}
		},
		{ auto: true }
	]
});

export { expect };
