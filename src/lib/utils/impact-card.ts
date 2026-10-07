import { wrapLines } from '$lib/utils/cards';
import { CHAR_W, INNER, clip, textWidth } from '$lib/utils/cards';

// The impact card's two rows of paper chips, each sized from its title's estimated width and
// ordered for the fewest crossing curves, and the curves from a citing chip's bottom centre to the
// top centre of each chip it cites.

export const CHIP = {
	pad: 12,
	titleSize: 15,
	line: 19,
	metaSize: 14,
	badgeSize: 13,
	badgeH: 20,
	badgePad: 7,
	h: 12 + 2 * 19 + 10 + 20 + 12
} as const;

export const ROWS = { summaryY: 16, topY: 34, bottomY: INNER.h - 30 - CHIP.h, labelY: INNER.h - 6 };

const GAP = 24;
const INSET = 2;
const MIN_W = 200;
const MIN_JOURNAL_CHARS = 12;
const MAX_W = { top: 440, bottom: 320 };

export type ChipBadge = { label: string; fill: string; ink: string };
export type ChipPaper = { title: string; year: number; journal: string; badges: ChipBadge[] };
export type PlacedBadge = ChipBadge & { x: number; w: number };
export type Chip = {
	x: number;
	y: number;
	w: number;
	lines: string[];
	year: string;
	journal: string;
	badges: PlacedBadge[];
};
export type ImpactLayout = { top: Chip[]; bottom: Chip[]; edges: string[] };

// `links` pairs a top chip's index with the index of a bottom chip it cites.
export function layoutImpact(
	top: ChipPaper[],
	bottom: ChipPaper[],
	links: [number, number][]
): ImpactLayout {
	const order = uncross(top.length, bottom.length, links);
	const topChips = layoutRow(
		order.top.map((i) => top[i]),
		ROWS.topY,
		MAX_W.top
	);
	const bottomChips = layoutRow(
		order.bottom.map((i) => bottom[i]),
		ROWS.bottomY,
		MAX_W.bottom
	);
	const edges = links.map(([t, b]) =>
		edgePath(topChips[order.top.indexOf(t)], bottomChips[order.bottom.indexOf(b)])
	);
	return { top: topChips, bottom: bottomChips, edges };
}

// The orders of both rows (at most MAX_TOP! × MAX_BOTTOM! pairs, the row caps of the impact card
// kind) with the fewest crossing curves, the given order where tied.
export function uncross(
	nTop: number,
	nBottom: number,
	links: [number, number][]
): { top: number[]; bottom: number[] } {
	let best = { top: [] as number[], bottom: [] as number[], crossings: Infinity };
	for (const top of permutations(nTop)) {
		for (const bottom of permutations(nBottom)) {
			const crossings = countCrossings(links, top, bottom);
			if (crossings < best.crossings) best = { top, bottom, crossings };
		}
	}
	return { top: best.top, bottom: best.bottom };
}

function countCrossings(links: [number, number][], top: number[], bottom: number[]): number {
	let n = 0;
	for (const [t1, b1] of links) {
		for (const [t2, b2] of links) {
			if ((top.indexOf(t1) - top.indexOf(t2)) * (bottom.indexOf(b1) - bottom.indexOf(b2)) < 0) n++;
		}
	}
	return n;
}

// Every order of 0..n-1, lexicographic from the identity.
function permutations(n: number): number[][] {
	const go = (rest: number[]): number[][] =>
		rest.length <= 1
			? [rest]
			: rest.flatMap((x, i) => go(rest.toSpliced(i, 1)).map((p) => [x, ...p]));
	return go([...Array(n).keys()]);
}

function layoutRow(papers: ChipPaper[], y: number, cap: number): Chip[] {
	const room = INNER.w - 2 * INSET;
	const maxW = Math.min(cap, (room - (papers.length - 1) * GAP) / papers.length);
	const widths = papers.map((p) => chipWidth(p, maxW));
	let x = INSET + (room - widths.reduce((a, b) => a + b, 0) - (papers.length - 1) * GAP) / 2;
	return papers.map((p, i) => {
		const chip = placeChip(p, x, y, widths[i]);
		x += widths[i] + GAP;
		return chip;
	});
}

function chipWidth(p: ChipPaper, maxW: number): number {
	const titleW = textWidth(p.title, CHIP.titleSize);
	const inner = maxW - 2 * CHIP.pad;
	const text = titleW <= inner ? titleW : Math.min(inner, titleW / 2 + 4 * CHIP.titleSize);
	const meta = textWidth(`${p.year}`, CHIP.metaSize, CHAR_W.mono) + badgesWidth(p.badges) + 60;
	return Math.min(maxW, Math.max(MIN_W, text, meta) + 2 * CHIP.pad);
}

function placeChip(p: ChipPaper, x: number, y: number, w: number): Chip {
	const inner = w - 2 * CHIP.pad;
	let bx = x + w - CHIP.pad;
	const badges = p.badges.map((b) => {
		const bw = badgeWidth(b);
		bx -= bw;
		const placed = { ...b, x: bx, w: bw };
		bx -= 6;
		return placed;
	});
	const year = `${p.year}`;
	const journalRoom =
		inner - textWidth(year, CHIP.metaSize, CHAR_W.mono) - 10 - badgesWidth(p.badges) - 8;
	const journalChars = Math.floor(journalRoom / (CHIP.metaSize * CHAR_W.sans));
	return {
		x,
		y,
		w,
		lines: wrapLines(p.title, Math.floor(inner / (CHIP.titleSize * CHAR_W.sans)), 2),
		year,
		journal: journalChars >= MIN_JOURNAL_CHARS ? clip(p.journal, journalChars) : '',
		badges
	};
}

function badgeWidth(b: ChipBadge): number {
	return textWidth(b.label, CHIP.badgeSize) + 2 * CHIP.badgePad;
}

function badgesWidth(badges: ChipBadge[]): number {
	return badges.reduce((sum, b) => sum + badgeWidth(b) + 6, 0);
}

function edgePath(from: Chip, to: Chip): string {
	const sx = from.x + from.w / 2;
	const sy = from.y + CHIP.h;
	const ex = to.x + to.w / 2;
	const ey = to.y;
	const bend = (ey - sy) * 0.45;
	return `M ${sx} ${sy} C ${sx} ${sy + bend}, ${ex} ${ey - bend}, ${ex} ${ey}`;
}
