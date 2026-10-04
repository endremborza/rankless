import { LATEST_YEAR } from '$lib/constants';
import { getColor } from '$lib/style-util';
import { formatNumber } from '$lib/text-format-util';
import type * as tt from '$lib/tree-types';
import { htmlToText } from '$lib/utils/paper-helpers';

// The hit-paper rainbow's chart space: x runs 0..xBase over the years shown, y runs -yBase..0 up
// to the most-cited paper, with padding around for the axis labels.
export const xPad = 2;
export const yPad = 2.5;
export const xBase = 26;
export const yBase = 12;

export const RAINBOW_SORTS = ['citations', 'score', 'year'] as const;
export type RainbowSort = (typeof RAINBOW_SORTS)[number];

export type PubMark = { x: number; color: string };
export type YTick = { label: string; y: number };
export type FigPaper = {
	i: number;
	rate: number;
	path: string;
	name: string;
	doi: string;
	endX: number;
	endY: number;
	pathName: string;
	year: number;
	citations: number;
};
export type FigureBasis = ReturnType<typeof getFigureBasis>;

export function rainbowPapers(papers: tt.Paper[], sortBy: RainbowSort): tt.Paper[] {
	return papers
		.filter((p) => p.yearlyCites && p.yearlyCites.length > 0)
		.toSorted((a, b) => {
			if (sortBy === 'score') return (b.score ?? -1) - (a.score ?? -1);
			if (sortBy === 'year') return b.year - a.year;
			return b.citations - a.citations;
		});
}

export function computeYearRates(papers: { year: number }[]): number[] {
	const n = papers.length;
	if (n <= 1) return papers.map(() => 0.5);
	const byYear = [...papers.keys()].sort((a, b) => papers[a].year - papers[b].year);
	const rates = new Array<number>(n);
	byYear.forEach((paperIdx, rank) => {
		rates[paperIdx] = rank / (n - 1);
	});
	return rates;
}

export function getVisInds(ps: tt.Paper[], first: number, n: number): number[] {
	const inds: number[] = [];
	for (let i = first; i < Math.min(ps.length, first + n); i++) inds.push(i);
	return inds;
}

export function niceYTickSteps(yMax: number): number[] {
	const roughStep = yMax / 4;
	const order = Math.floor(Math.log10(roughStep));
	for (const exp of [order + 1, order, order - 1]) {
		const mag = Math.pow(10, exp);
		for (const m of [5, 4, 2.5, 2, 1]) {
			const step = m * mag;
			if (step <= 0) continue;
			const count = Math.floor(yMax / step);
			if (count >= 3 && count <= 5) {
				return Array.from({ length: count }, (_, i) => Math.round((i + 1) * step));
			}
		}
	}
	return [0.25, 0.5, 0.75, 1].map((f) => Math.round(f * yMax));
}

export function logYTickSteps(yMax: number): number[] {
	const steps: number[] = [];
	for (let p = 1; p <= yMax; p *= 10) steps.push(p);
	return steps;
}

export function getFigureBasis(
	ps: tt.Paper[],
	inds: number[],
	globalMin: number,
	align: boolean,
	rates: number[],
	log: boolean
) {
	const nVis = inds.length;
	const yearSpan = LATEST_YEAR - globalMin;
	const xScale = Math.max(yearSpan, 1) / xBase;

	const width = xBase + xPad + 5;
	const height = yBase + yPad * 2;
	const aspect = width / height;
	const xMin = -xPad;
	const yMin = -height + yPad;

	const yTransform = log ? (v: number) => Math.log2(v + 1) : (v: number) => v;
	let yMax = 0;
	for (const i of inds) yMax = Math.max(yMax, ps[i].citations);
	if (yMax === 0) yMax = 1;
	const yScale = yTransform(yMax) / yBase;

	const figPapers: FigPaper[] = [];
	const pubMarks: PubMark[] = [];

	for (let vi = 0; vi < nVis; vi++) {
		const i = inds[vi];
		const paper = ps[i];
		const yc = paper.yearlyCites ?? [];
		const startYear = paper.year - globalMin;
		const lifespan = Math.max(LATEST_YEAR - paper.year + 1, 1);
		const rate = rates[i];

		let endX = 0,
			endY = 0;
		let cumSum = 0;
		const pBasis: string[] = [];

		for (let y = 0; y < yc.length && y < lifespan; y++) {
			cumSum += yc[y];
			const xPos = ((align ? 0 : startYear) + y) / xScale;
			const yVal = -(yTransform(cumSum) / yScale);
			endX = xPos;
			endY = yVal;
			pBasis.push(`${y === 0 ? 'M' : 'L'} ${xPos.toFixed(3)} ${yVal.toFixed(3)}`);
		}

		const markerX = align ? 0 : startYear / xScale;
		pubMarks.push({ x: markerX, color: getColor(rate) });

		if (pBasis.length === 1) {
			pBasis.push(`L ${(endX + 0.5).toFixed(3)} ${endY.toFixed(3)}`);
		}

		const nYears = Math.min(yc.length, lifespan);
		const pathHorizLen = (nYears - 1) / xScale;
		const maxChars = Math.max(8, Math.min(60, Math.round(pathHorizLen * 3.5)));
		const plainName = htmlToText(paper.name);
		const pathName =
			plainName.length > maxChars ? plainName.slice(0, maxChars - 3) + '...' : plainName;

		figPapers.push({
			i,
			rate,
			path: pBasis.join(' '),
			name: paper.name,
			doi: paper.doi,
			endX,
			endY: Math.max(endY, -yBase + 0.8),
			pathName,
			year: paper.year,
			citations: paper.citations
		});
	}

	const yearTicks: { name?: string | number; x: number }[] = [];
	const toT = (i: number, k: number) => i === Math.floor((k * yearSpan) / 3);
	if (align) {
		yearTicks.push({ name: 0, x: 0 });
		for (let i = 1; i < yearSpan; i++) {
			yearTicks.push({
				name: toT(i, 1) || toT(i, 2) ? `+${i}` : undefined,
				x: i / xScale
			});
		}
	} else {
		yearTicks.push({ name: globalMin, x: 0 }, { name: LATEST_YEAR, x: xBase });
		for (let i = 1; i < yearSpan; i++) {
			yearTicks.push({
				name: toT(i, 1) || toT(i, 2) ? globalMin + i : undefined,
				x: i / xScale
			});
		}
	}

	const yTicks: YTick[] = [];
	for (const val of log ? logYTickSteps(yMax) : niceYTickSteps(yMax)) {
		yTicks.push({ label: formatNumber(val), y: -(yTransform(val) / yScale) });
	}

	return { width, height, xMin, yMin, figPapers, yearTicks, yTicks, pubMarks, aspect, align };
}

export function tipLabelPos(hp: FigPaper): { x: number; y: number; anchor: 'start' | 'end' } {
	const estWidth = formatNumber(hp.citations).length * 0.36 + 0.3;
	if (hp.endX + estWidth <= xBase) {
		return { x: hp.endX + 0.2, y: hp.endY + 0.15, anchor: 'start' };
	}
	// Near the right edge the value would run into the y-axis labels; anchor it at the tip and
	// lift it just above the line so it stays inside the plot.
	return { x: hp.endX, y: hp.endY - 0.3, anchor: 'end' };
}
