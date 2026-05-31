const STOP = /^(and|of|the|in|for|a|an|at|by|to)$/i;

// Categorical palette for comparison subfields. Spread across the --color-range ramp so adjacent
// selections stay distinguishable; the first DEFAULT_FIELD_N keep the original well-balanced look.
export const SUBFIELD_COLOR_VARS: readonly string[] = [
	'--color-range-15',
	'--color-range-35',
	'--color-range-50',
	'--color-range-70',
	'--color-range-90',
	'--color-range-25',
	'--color-range-60',
	'--color-range-80'
];

export function abbrSfName(name: string): string {
	const significant = name.split(/\s+/).filter((w) => !STOP.test(w));
	if (significant.length === 0) return name.slice(0, 5).toUpperCase();
	if (significant.length === 1) return significant[0].slice(0, 5).toUpperCase();
	return significant
		.map((w) => w[0])
		.join('')
		.toUpperCase();
}

export function sfColorVar(displayIdx: number): string {
	return SUBFIELD_COLOR_VARS[displayIdx % SUBFIELD_COLOR_VARS.length];
}

// Cohort noun per root entity type, for framing standings ("top 5% of <noun> ...").
const COHORT_NOUN: Record<string, string> = {
	authors: 'authors',
	institutions: 'institutions',
	countries: 'countries',
	sources: 'journals'
};

// Build the tier labels from the ladder's percentile bands so they never drift from the
// backend: "top 20%" … "top 0.01%".
export function tierLabels(pctBands: number[]): string[] {
	return pctBands.map((p) => `top ${Number((p * 100).toFixed(4))}%`);
}

// Most selective tier (1-based) a citation count reaches within a subfield, given that subfield's
// breakpoint row from /v1/ladder; 0 = none.
export function citStandingTier(ladderRow: (number | null)[], c: number): number {
	if (c <= 0) return 0;
	let bestTier = 0;
	let bestThr = 0;
	for (let i = 0; i < ladderRow.length; i++) {
		const thr = ladderRow[i];
		if (thr != null && c >= thr && (bestTier === 0 || thr >= bestThr)) {
			bestThr = thr;
			bestTier = i + 1;
		}
	}
	return bestTier;
}

export function standingLabel(tier: number, labels: string[]): string | null {
	if (tier < 1 || tier > labels.length) return null;
	return labels[tier - 1];
}

export function standingPhrase(
	tier: number,
	labels: string[],
	rootType: string,
	subfieldName: string
): string | null {
	const label = standingLabel(tier, labels);
	if (!label) return null;
	const noun = COHORT_NOUN[rootType] ?? 'entities';
	return `${label} most cited of all ${noun} in ${subfieldName}`;
}

// Map a peer/hero ratio to a bar height (% of plot), pinning the hero's 1× line at `baselinePct`
// regardless of the chart's own spread, so the baseline aligns across charts. Below 1× scales
// linearly into the baseline; above 1× scales linearly up to the chart's max ratio.
export function ratioBarHeight(ratio: number, maxRatio: number, baselinePct: number): number {
	if (ratio <= 1) return baselinePct * ratio;
	return baselinePct + ((100 - baselinePct) * (ratio - 1)) / (maxRatio - 1);
}
