import type { PlaywrightTestConfig } from '@playwright/test';
import dev from './src/lib/assets/data/dev.json' with { type: 'json' };

// No webServer here — the Python orchestrator (pyscripts/mega_test.py) manages
// the dev server lifecycle.
const config: PlaywrightTestConfig = {
	testDir: 'tests',
	testMatch: 'ledger.spec.ts',
	use: {
		baseURL: process.env.BASE_URL || `http://localhost:${dev.devPort}`
	}
};

export default config;
