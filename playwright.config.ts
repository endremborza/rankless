import type { PlaywrightTestConfig } from '@playwright/test';
import dev from './src/lib/assets/data/dev.json' with { type: 'json' };
import { E2E_ENV } from './tests/e2e-env';

const config: PlaywrightTestConfig = {
	webServer: {
		command: 'bun tests/seed-game.ts && bun run build && bun run preview',
		port: dev.previewPort,
		env: E2E_ENV
	},
	testDir: 'tests',
	testMatch: /(.+\.)?(test|spec)\.[jt]s/,
	// ledger.spec.ts is an integration test driven by pyscripts/mega_test.py via
	// playwright.ledger.config.ts (needs a live backend + a pipeline run between
	// its two phases). Exclude it from the standalone `bun run test` suite.
	testIgnore: 'ledger.spec.ts'
};

export default config;
