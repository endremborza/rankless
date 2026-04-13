import type { EntityPeersResp } from '$lib/tree-types';

const STOP = /^(and|of|the|in|for|a|an|at|by|to)$/i;

export function abbrSfName(name: string): string {
	const significant = name.split(/\s+/).filter((w) => !STOP.test(w));
	if (significant.length === 0) return name.slice(0, 5);
	if (significant.length === 1) return significant[0].slice(0, 5);
	return significant.map((w) => w[0]).join('');
}

export function sparkLinePath(vals: number[], max: number): string {
	if (!vals.length || max === 0) return '';
	return vals.map((v, i) => `${i === 0 ? 'M' : 'L'} ${i} ${(1 - v / max).toFixed(3)}`).join(' ');
}

export function sparkAreaPath(vals: number[], max: number): string {
	if (!vals.length || max === 0) return '';
	const line = vals
		.map((v, i) => `${i === 0 ? 'M' : 'L'} ${i} ${(1 - v / max).toFixed(3)}`)
		.join(' ');
	return `${line} L ${vals.length - 1} 1 L 0 1 Z`;
}

export function sfOpacity(val: number, max: number): number {
	if (max === 0) return 0;
	return 0.1 + 0.9 * (val / max);
}

// yearCentroid 0=early(orange) → 1=late(blue-purple)
export function centroidColor(c: number): string {
	const r = Math.round(200 + (75 - 200) * c);
	const g = Math.round(132 + (88 - 132) * c);
	const b = Math.round(55 + (180 - 55) * c);
	return `rgb(${r},${g},${b})`;
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

// Polygon path for radar chart (fraction of radius per axis)
export function radarPath(values: number[], maxes: number[], r = 42, cx = 50, cy = 50): string {
	if (!values.length) return '';
	return (
		'M ' +
		values
			.map((v, i) => {
				const angle = (Math.PI * 2 * i) / values.length - Math.PI / 2;
				const frac = maxes[i] > 0 ? v / maxes[i] : 0;
				return `${(cx + r * frac * Math.cos(angle)).toFixed(1)} ${(cy + r * frac * Math.sin(angle)).toFixed(1)}`;
			})
			.join(' L ') +
		' Z'
	);
}

// Outer pentagon outline (full radius)
export function pentagonPath(r = 42, cx = 50, cy = 50, n = 5): string {
	return (
		'M ' +
		Array.from({ length: n }, (_, i) => {
			const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
			return `${(cx + r * Math.cos(angle)).toFixed(1)} ${(cy + r * Math.sin(angle)).toFixed(1)}`;
		}).join(' L ') +
		' Z'
	);
}

// Label positions for radar axes
export function radarLabelPos(i: number, n: number, r = 49, cx = 50, cy = 50): [number, number] {
	const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
	return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
}
