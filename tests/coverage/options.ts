import type { CoverageReportOptions } from 'monocart-coverage-reports';

// Shared across the per-test browser collector (fixtures) and the merge step
// (global-teardown). Both instantiate CoverageReport with these options against
// the same outputDir, so monocart aggregates every worker's data from its cache.
export const coverageOptions: CoverageReportOptions = {
	name: 'Rankless E2E Coverage',
	outputDir: 'coverage-e2e',
	reports: ['v8', 'html', 'console-summary'],
	entryFilter: (entry) => !entry.url.includes('node_modules'),
	sourceFilter: (sourcePath) =>
		/(^|\/)src\//.test(sourcePath) && !sourcePath.includes('node_modules')
};
