import type { PlaywrightTestConfig } from '@playwright/test';

// E2E coverage run: `bun run test:e2e:cov`.
//
// Same specs as the default config, but the app is built with inline sourcemaps
// (COVERAGE=1) so monocart can remap Chromium's V8 coverage back to .svelte/.ts.
// The fixture collects per-test browser coverage; global-teardown merges + renders.
//
// Only browser-side execution is captured. The SSR/load side runs under bun (the
// app imports bun:sqlite), which has no NODE_V8_COVERAGE equivalent — see
// docs/architecture.md. Component code is still covered here via hydration.
const config: PlaywrightTestConfig = {
	testDir: 'tests',
	testMatch: /(.+\.)?(test|spec)\.[jt]s/,
	testIgnore: 'ledger.spec.ts',
	globalSetup: './tests/coverage/global-setup.ts',
	globalTeardown: './tests/coverage/global-teardown.ts',
	webServer: {
		command: 'bun run build && bun run preview',
		port: 4173,
		reuseExistingServer: false,
		timeout: 180_000,
		env: { COVERAGE: '1' }
	}
};

export default config;
