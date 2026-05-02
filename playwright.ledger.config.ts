import type { PlaywrightTestConfig } from '@playwright/test';

// No webServer here — the Python orchestrator (pyscripts/mega_test.py) manages
// the dev server lifecycle.
const config: PlaywrightTestConfig = {
	testDir: 'tests',
	testMatch: 'ledger.spec.ts',
	use: {
		baseURL: process.env.BASE_URL || 'http://localhost:5173'
	}
};

export default config;
