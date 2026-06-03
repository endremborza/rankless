import { CoverageReport } from 'monocart-coverage-reports';
import { coverageOptions } from './options';

// Clear any previous run before workers start adding browser coverage.
export default function globalSetup(): void {
	new CoverageReport(coverageOptions).cleanCache();
}
