import { formatNumber } from '$lib/text-format-util';

// Round gridline values strictly inside (0, max) so bars can be gauged against them.
export function niceTicks(max: number, target = 3): number[] {
	if (max <= 0) return [];
	const raw = max / (target + 1);
	const mag = Math.pow(10, Math.floor(Math.log10(raw)));
	const norm = raw / mag;
	const step = (norm >= 5 ? 10 : norm >= 2.5 ? 5 : norm >= 2 ? 2.5 : norm >= 1 ? 2 : 1) * mag;
	const out: number[] = [];
	for (let v = step; v < max; v += step) out.push(v);
	return out;
}

// As many gridlines (1–3) as fit a bar span of `px` without their `textPx` labels colliding.
export function tickCount(px: number, textPx: number): number {
	return Math.min(3, Math.max(1, Math.floor(px / (textPx * 1.7))));
}

// The labelled gridlines of a bar span `px` tall reaching `max`, at whole counts only.
export function countGrid(max: number, px: number, textPx: number): { v: number; label: string }[] {
	return niceTicks(max, tickCount(px, textPx))
		.filter(Number.isInteger)
		.map((v) => ({ v, label: formatNumber(v) }));
}

// The calendar years of an `n`-long yearly series ending at `end`.
export function seriesYears(n: number, end: number): number[] {
	return Array.from({ length: n }, (_, i) => end - (n - 1) + i);
}
