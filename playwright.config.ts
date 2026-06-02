import type { PlaywrightTestConfig } from '@playwright/test';

const config: PlaywrightTestConfig = {
	webServer: {
		command: 'bun run build && bun run preview',
		port: 4173
	},
	testDir: 'tests',
	testMatch: /(.+\.)?(test|spec)\.[jt]s/,
	// ledger.spec.ts is an integration test driven by pyscripts/mega_test.py via
	// playwright.ledger.config.ts (needs a live backend + a pipeline run between
	// its two phases). Exclude it from the standalone `bun run test` suite.
	testIgnore: 'ledger.spec.ts'
};

export default config;
