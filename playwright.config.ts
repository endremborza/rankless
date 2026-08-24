import type { PlaywrightTestConfig } from '@playwright/test';

const config: PlaywrightTestConfig = {
	webServer: {
		command: 'bun tests/seed-game.ts && bun run build && bun run preview',
		port: 4173,
		// Scratch user DB + object store, so seeded game fixtures never land in
		// the real data/ files (which ride the cross-box handoff).
		env: {
			RANKLESS_DB_PATH: '.e2e-data/rankless.sqlite',
			MCP_OBJECTS_ROOT: '.e2e-data/mcp-objects'
		}
	},
	testDir: 'tests',
	testMatch: /(.+\.)?(test|spec)\.[jt]s/,
	// ledger.spec.ts is an integration test driven by pyscripts/mega_test.py via
	// playwright.ledger.config.ts (needs a live backend + a pipeline run between
	// its two phases). Exclude it from the standalone `bun run test` suite.
	testIgnore: 'ledger.spec.ts'
};

export default config;
