import { CoverageReport } from 'monocart-coverage-reports';
import { coverageOptions } from './options';

// Browser coverage was added per-test by the fixture (into the shared cache);
// render the report from it.
export default async function globalTeardown(): Promise<void> {
	const results = await new CoverageReport(coverageOptions).generate();
	if (results) {
		const { lines, statements } = results.summary;
		console.log(
			`\nE2E coverage → ${results.reportPath}\n` +
				`  lines ${lines.pct}%  statements ${statements.pct}%`
		);
	}
}
