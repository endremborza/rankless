import countryPaths from '$lib/assets/data/country-svg-paths.json';
import { nodes as nodesData, edges } from '$lib/assets/data/concept-map.json';
import { formatNumber } from '$lib/text-format-util';
import { CHAR_W, INNER, clipToWidth, textWidth } from '$lib/utils/cards';
import { overlaps, placeGreedy, type Box } from '$lib/utils/label-placement';
import {
	ORDERED_DOMAINS,
	SUBFIELD_NULL_R,
	domainRate,
	subfieldColor,
	type CountryStyles,
	type SubfieldStyle
} from '$lib/utils/flat-out-styles';
import { getColor } from '$lib/style-util';

// Layout of the two flat-out share cards (the world map, the concept map of fields) in card
// pixels: the projection of each asset into the card, the labels of the heaviest and the
// highlighted items placed where they collide with nothing, and the legends.

type Point = { x: number; y: number };
// A label box to place beside its anchor, or centred on it when it fits the thing it names.
export type LabelAsk = { anchor: Point; w: number; h: number; gap: number; centred: boolean };
// `align` is the text-anchor that keeps the label's text against its anchor whatever the error of
// the width estimate.
export type Placed = Box & { offset: boolean; align: 'start' | 'middle' | 'end' };
export type CardLabel = Placed & {
	anchor: Point;
	name: string;
	value: string;
	hl: boolean;
	// Where the text is anchored for `align`, and its baseline.
	tx: number;
	ty: number;
};

export type MapCardProps = {
	transform: string;
	shades: Record<string, { fill: string; opacity: number }>;
	hl: string[];
	// Stroke widths in the map's units.
	strokes: { border: number; hl: number };
	labels: CardLabel[];
	legend: { title: string; y: number; rows: LegendRow[] };
};
export type LegendRow = { y: number; text: string; fill: string; opacity: number };

export type FieldNode = Point & { r: number; fill: string; sat: number; hl: boolean };
export type FieldsCardProps = {
	nodes: FieldNode[];
	edges: [number, number, number, number][];
	labels: CardLabel[];
	domains: { name: string; fill: string }[];
	sizeText: string;
};

export const LABEL_TEXT = 16;
export const VALUE_TEXT = 14;
export const LEGEND_TEXT = 15;
const LABEL_H = 20;
// Kept between labels, as their widths are estimates.
const LABEL_MARGIN = 6;
export const VALUE_GAP = 7;
const TOP_COUNTRIES = 5;
// A label is centred on its country, with no dot, while it overhangs the country by at most this.
const CENTRED_OVERHANG = 1.3;
const DOT_GAP = 7;
const TOP_FIELDS = 6;
const FIELD_NAME_MAX = 250;

// The map's land spans x 0–2000, y 0–860 of the asset's units; it is fitted to the card's height.
const MAP_VIEW = { w: 2000, h: 860 };
const MAP_SCALE = INNER.h / MAP_VIEW.h;
const MAP_X = (INNER.w - MAP_VIEW.w * MAP_SCALE) / 2;
const LEGEND_ROW = 22;
export const LEGEND_SWATCH = { w: 26, h: 16, gap: 8 };

// The concept map's nodes span x 0–130, y 0–100; the layout is stretched into the plot so the
// labels get room, and radii scale by the mean of the two axes.
export const FIELDS_PLOT_W = 760;
const FIELDS_PAD = 16;
const FIELDS_SX = (FIELDS_PLOT_W - 2 * FIELDS_PAD) / 130;
const FIELDS_SY = (INNER.h - 2 * FIELDS_PAD) / 100;
const FIELDS_R = (FIELDS_SX + FIELDS_SY) / 2;

const nodes = nodesData as Record<string, number[]>;

// Where each country's label goes: the centroid of its largest outline and that outline's width,
// in card pixels.
const COUNTRY_ANCHORS: Record<string, Point & { span: number }> = Object.fromEntries(
	Object.entries(countryPaths).map(([name, ds]) => {
		const { x, y, span } = largestOutline(ds.flatMap(rings));
		return [name, { x: MAP_X + x * MAP_SCALE, y: y * MAP_SCALE, span: span * MAP_SCALE }];
	})
);

export function mapCardLayout(styles: CountryStyles, hl: string[], title: string): MapCardProps {
	const top0 = INNER.h - LEGEND_ROW * (styles.buckets.length + 1);
	const rows = styles.buckets.map((b, i) => ({
		y: top0 + LEGEND_ROW * (i + 1) + (LEGEND_ROW - LEGEND_SWATCH.h) / 2,
		text: `${formatNumber(b.lo)} – ${formatNumber(b.hi)}`,
		fill: b.shade.fill,
		opacity: b.shade.opacity
	}));
	const rowW = (text: string) =>
		LEGEND_SWATCH.w + LEGEND_SWATCH.gap + textWidth(text, LEGEND_TEXT, CHAR_W.mono);
	const legendBox = {
		x: 0,
		y: top0,
		w: Math.max(textWidth(title, LEGEND_TEXT), ...rows.map((r) => rowW(r.text))),
		h: INNER.h - top0
	};
	const drawn = (name: string) => name in COUNTRY_ANCHORS;
	const top = Object.entries(styles.byName)
		.filter(([name]) => drawn(name) && !hl.includes(name))
		.sort(([, a], [, b]) => b.w - a.w)
		.slice(0, TOP_COUNTRIES)
		.map(([name]) => name);
	const hlDrawn = hl.filter(drawn);
	const wanted = [...hlDrawn, ...top];
	const texts = wanted.map((name) => {
		const w = styles.byName[name]?.w;
		return { name, value: w == undefined ? '' : formatNumber(w) };
	});
	// A highlighted country is marked by its outline, so its label clears the outline instead of
	// pointing at a dot.
	const asks = texts.map(({ name, value }, i) => {
		const w = labelWidth(name, value);
		const anchor = COUNTRY_ANCHORS[name];
		const gap = i < hlDrawn.length ? Math.max(DOT_GAP, anchor.span / 2 + 5) : DOT_GAP;
		return { anchor, w, h: LABEL_H, gap, centred: w <= anchor.span * CENTRED_OVERHANG };
	});
	const dots = asks.map(({ anchor: { x, y } }) => ({ x: x - 4, y: y - 4, w: 8, h: 8 }));
	const bounds = { x: 0, y: 0, w: INNER.w, h: INNER.h };
	const placed = placeLabels(asks, hlDrawn.length, bounds, [legendBox], dots);
	return {
		transform: `translate(${MAP_X} 0) scale(${MAP_SCALE})`,
		shades: Object.fromEntries(
			Object.entries(styles.byName).map(([name, s]) => [name, { fill: s.fill, opacity: s.opacity }])
		),
		hl,
		strokes: { border: 0.6 / MAP_SCALE, hl: 2.2 / MAP_SCALE },
		labels: collect(placed, asks, texts, hlDrawn.length),
		legend: { title, y: top0 + LEGEND_TEXT, rows }
	};
}

export function fieldsCardLayout(
	styles: Record<string, SubfieldStyle>,
	hl: string[],
	names: Record<string, string>,
	sizeText: string
): FieldsCardProps {
	const project = ([x, y]: number[]) => ({
		x: FIELDS_PAD + x * FIELDS_SX,
		y: FIELDS_PAD + y * FIELDS_SY
	});
	const fieldNodes = Object.entries(nodes).map(([sfi, xy]) => ({
		...project(xy),
		r: (styles[sfi]?.r ?? SUBFIELD_NULL_R) * FIELDS_R,
		fill: subfieldColor(Number(sfi)),
		sat: styles[sfi]?.sat ?? 1,
		hl: hl.includes(sfi),
		sfi
	}));
	const bySfi = Object.fromEntries(fieldNodes.map((n) => [n.sfi, n]));
	const top = Object.entries(styles)
		.filter(([sfi]) => sfi in bySfi && !hl.includes(sfi))
		.sort(([, a], [, b]) => b.w - a.w)
		.slice(0, TOP_FIELDS)
		.map(([sfi]) => sfi);
	const hlDrawn = hl.filter((sfi) => sfi in bySfi);
	const wanted = [...hlDrawn, ...top];
	const texts = wanted.map((sfi) => {
		const w = styles[sfi]?.w;
		const value = w == undefined ? '' : formatNumber(w);
		const room = FIELD_NAME_MAX - (value ? textWidth(value, VALUE_TEXT, CHAR_W.mono) : 0);
		const name = clipToWidth(names[sfi] ?? '', room, LABEL_TEXT);
		return { name, value };
	});
	const asks = wanted.map((sfi, i) => ({
		anchor: bySfi[sfi],
		w: labelWidth(texts[i].name, texts[i].value),
		h: LABEL_H,
		gap: bySfi[sfi].r + 4,
		centred: false
	}));
	const circles = wanted.map((sfi) => {
		const { x, y, r } = bySfi[sfi];
		return { x: x - r, y: y - r, w: 2 * r, h: 2 * r };
	});
	const bounds = { x: 0, y: 0, w: FIELDS_PLOT_W, h: INNER.h };
	const placed = placeLabels(asks, hlDrawn.length, bounds, [], circles);
	return {
		nodes: [...fieldNodes.filter((n) => !n.hl), ...fieldNodes.filter((n) => n.hl)],
		edges: edges.map(([s, t]) => {
			const [a, b] = [project(nodes[s]), project(nodes[t])];
			return [a.x, a.y, b.x, b.y];
		}),
		labels: collect(placed, asks, texts, hlDrawn.length),
		domains: ORDERED_DOMAINS.map((name, i) => ({ name, fill: getColor(domainRate(i + 1)) })),
		sizeText
	};
}

// Greedy in the asks' order (heaviest first): each label takes its first candidate spot inside
// `bounds` that overlaps no placed label, no obstacle and no other live ask's mark (`marks[i]` is
// the box of ask i's own dot or circle); a label with no such spot is dropped. The first `nMust`
// labels are never dropped: they settle for a spot clear of the placed labels only, and failing
// that for their first spot.
export function placeLabels(
	asks: LabelAsk[],
	nMust: number,
	bounds: Box,
	obstacles: Box[],
	marks: Box[]
): (Placed | null)[] {
	const spots = asks.map((ask, i) => {
		const within = candidates(ask).filter((c) => inside(c, bounds));
		return within.length > 0 || i >= nMust ? within : [clampInto(candidates(ask)[0], bounds)];
	});
	const picks = placeGreedy(
		spots.map((boxes, i) => ({ boxes, must: i < nMust })),
		(i, dropped) => [...obstacles, ...marks.filter((_, j) => j !== i && !dropped.has(j))],
		(a, b) => overlaps(a, b, LABEL_MARGIN, LABEL_MARGIN / 2)
	);
	return picks.map((pick, i) => (pick === null ? null : spots[i][pick]));
}

function collect(
	placed: (Placed | null)[],
	asks: LabelAsk[],
	texts: { name: string; value: string }[],
	nMust: number
): CardLabel[] {
	const tx = (p: Placed) => p.x + { start: 0, middle: p.w / 2, end: p.w }[p.align];
	return placed.flatMap((p, i) =>
		p
			? [{ ...p, anchor: asks[i].anchor, ...texts[i], hl: i < nMust, tx: tx(p), ty: p.y + p.h - 5 }]
			: []
	);
}

function labelWidth(name: string, value: string): number {
	const valueW = value ? VALUE_GAP + textWidth(value, VALUE_TEXT, CHAR_W.mono) : 0;
	return textWidth(name, LABEL_TEXT) + valueW;
}

function candidates({ anchor: { x, y }, w, h, gap, centred }: LabelAsk): Placed[] {
	const d = gap * 0.7;
	const around: [number, number, Placed['align']][] = [
		[x + gap, y - h / 2, 'start'],
		[x - gap - w, y - h / 2, 'end'],
		[x + d, y - d - h, 'start'],
		[x + d, y + d, 'start'],
		[x - d - w, y - d - h, 'end'],
		[x - d - w, y + d, 'end'],
		[x - w / 2, y - gap - h, 'middle'],
		[x - w / 2, y + gap, 'middle']
	];
	const spots = around.map(([sx, sy, align]) => ({ x: sx, y: sy, w, h, offset: true, align }));
	if (!centred) return spots;
	return [{ x: x - w / 2, y: y - h / 2, w, h, offset: false, align: 'middle' }, ...spots];
}

function inside(a: Box, b: Box): boolean {
	return a.x >= b.x && a.y >= b.y && a.x + a.w <= b.x + b.w && a.y + a.h <= b.y + b.h;
}

function clampInto<T extends Box>(a: T, b: Box): T {
	return {
		...a,
		x: Math.min(Math.max(a.x, b.x), b.x + b.w - a.w),
		y: Math.min(Math.max(a.y, b.y), b.y + b.h - a.h)
	};
}

// The closed outlines of a path made of M/m, L/l and Z/z commands.
function rings(d: string): Point[][] {
	const tokens = d.match(/[MmLlZz]|-?\d*\.?\d+(?:e[-+]?\d+)?/g) ?? [];
	const out: Point[][] = [];
	let ring: Point[] = [];
	let [cmd, x, y, x0, y0] = ['M', 0, 0, 0, 0];
	for (let i = 0; i < tokens.length; ) {
		const t = tokens[i];
		if (/^[a-z]$/i.test(t)) {
			cmd = t;
			i++;
			if (cmd === 'z' || cmd === 'Z') {
				if (ring.length > 2) out.push(ring);
				[ring, x, y] = [[], x0, y0];
			}
			continue;
		}
		const rel = cmd === cmd.toLowerCase();
		[x, y] = [Number(t) + (rel ? x : 0), Number(tokens[i + 1]) + (rel ? y : 0)];
		i += 2;
		if (cmd === 'M' || cmd === 'm') {
			if (ring.length > 2) out.push(ring);
			[ring, x0, y0, cmd] = [[], x, y, rel ? 'l' : 'L'];
		}
		ring.push({ x, y });
	}
	if (ring.length > 2) out.push(ring);
	return out;
}

// The area centroid (shoelace) and the width of the largest ring.
function largestOutline(rs: Point[][]): Point & { span: number } {
	let best = { area: 0, x: 0, y: 0, span: 0 };
	for (const r of rs) {
		let [a, cx, cy] = [0, 0, 0];
		for (let i = 0; i < r.length; i++) {
			const [p, q] = [r[i], r[(i + 1) % r.length]];
			const cross = p.x * q.y - q.x * p.y;
			[a, cx, cy] = [a + cross, cx + (p.x + q.x) * cross, cy + (p.y + q.y) * cross];
		}
		if (Math.abs(a) <= Math.abs(best.area)) continue;
		const xs = r.map((p) => p.x);
		best = { area: a, x: cx / (3 * a), y: cy / (3 * a), span: Math.max(...xs) - Math.min(...xs) };
	}
	return best;
}
