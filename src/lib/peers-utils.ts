import type { EntityPeersResp } from '$lib/tree-types';

const STOP = /^(and|of|the|in|for|a|an|at|by|to)$/i;

export const SUBFIELD_COLOR_VARS: readonly string[] = [
	'--color-range-15',
	'--color-range-35',
	'--color-range-50',
	'--color-range-70',
	'--color-range-90'
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

export function sparkLinePath(vals: number[], max: number): string {
	if (!vals.length || max === 0) return '';
	return vals.map((v, i) => `${i === 0 ? 'M' : 'L'} ${i} ${(1 - v / max).toFixed(3)}`).join(' ');
}

export function globalCitesMax(data: EntityPeersResp): number {
	const all = [data.hero, ...data.peers];
	return Math.max(1, ...all.flatMap((e) => e.yearlyCites));
}

export function sfMaxes(data: EntityPeersResp): number[] {
	const all = [data.hero, ...data.peers];
	return data.topSubfields.map((_, si) =>
		Math.max(1, ...all.map((e) => e.subfieldCitations[si] ?? 0))
	);
}
