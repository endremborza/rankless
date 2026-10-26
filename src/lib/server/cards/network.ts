import type { PostAttRelatedEntity } from '$lib/wire/rankless_server/responses';
import { error } from '@sveltejs/kit';
import { getIndex, hubLayout, type Tie } from '$lib/network-util';
import { lastWord } from '$lib/text-format-util';
import { htmlToText } from '$lib/utils/paper-helpers';
import { CHAR_W, INNER, labelSize, textWidth } from '$lib/utils/cards';
import { placeGreedy, type Box } from '$lib/utils/label-placement';
import NetworkCard from '$lib/components/cards/NetworkCard.svelte';
import { CARD_SPEC, idsParam, intParam, type CardKind } from './kind';

export type NetLabel = {
	text: string;
	x: number;
	y: number;
	anchor: 'start' | 'middle' | 'end';
	size: number;
	box: Box;
};
export type NetHub = { x: number; y: number; r: number; label: NetLabel | null };
export type NetNode = NetHub & { on: boolean };
export type NetEdge = { x1: number; y1: number; x2: number; y2: number; rate: number; on: boolean };
type Spot = { side: -1 | 0 | 1; up: boolean };

const P = CARD_SPEC.network.params;
const R_MIN = 6;
const R_MAX = 24;
const HUB_R = 12;
const HUB_LABEL_MAX = 20;
const LABEL_MAX = 15;
const LABEL_GAP = 6;
const LABEL_PAD = 3;
const MARGIN_X = 150;
const MARGIN_Y = R_MAX + LABEL_GAP + LABEL_MAX * 1.1;
const FULL_NAMES = 3;
// A node this far towards the ring's side puts its label beside it, the rest above or below.
const SIDE_DIR = 0.6;
const SPOTS: Spot[] = [
	{ side: 0, up: true },
	{ side: 0, up: false },
	{ side: 1, up: false },
	{ side: -1, up: false }
];
const HUB_SPOTS: Spot[] = [
	{ side: 1, up: false },
	{ side: -1, up: false },
	{ side: 0, up: false },
	{ side: 0, up: true }
];

// The author's co-author network around the author: `n` first (ranked) co-authors and `with`
// ones highlighted with their ties.
export const network: CardKind = {
	component: NetworkCard,
	async load({ params, view }) {
		if (!view) error(404, 'no such card');
		const all = view.relations['paper-authors'] ?? [];
		const n = intParam(params, 'n', P.n.default, P.n.min, P.n.max);
		const authors = all.slice(0, n);
		const withIds = idsParam(params, 'with', n);
		if (authors.length < P.n.min) error(404, 'card unavailable');
		if (withIds.some((id) => !authors.some((a) => a.semanticId === id)))
			error(404, 'unknown co-author');
		const name = htmlToText(view.name);
		return {
			props: layoutNetwork(name, authors, all.length, view.authorNetwork, new Set(withIds)),
			caption: `Co-authors, sized by papers shared with ${name}; ties show the pair's joint papers`
		};
	}
};

// The author at the centre, the co-authors around them in a force layout (`hubLayout`), sized by
// papers shared with the author and pulled together by their own joint papers. A label goes on the
// side away from the author, or beside or across the node when that spot is taken; one with no free
// spot (clear of the nodes and of the labels of the author, the highlighted, then the bigger nodes)
// is left out.
export function layoutNetwork(
	name: string,
	authors: PostAttRelatedEntity[],
	total: number,
	weights: number[],
	highlight: Set<string>
): { hub: NetHub; nodes: NetNode[]; edges: NetEdge[] } {
	const counts = authors.map((a) => a.count ?? 0);
	const maxCount = Math.max(1, ...counts);
	const ties: Tie[] = [];
	for (let i = 0; i < authors.length; i++)
		for (let j = i + 1; j < authors.length; j++) {
			const w = weights[getIndex(i, j, total)] ?? 0;
			if (w > 0) ties.push({ i, j, rate: w });
		}
	const maxW = Math.max(1, ...ties.map((t) => t.rate));
	for (const t of ties) t.rate = Math.sqrt(t.rate / maxW);

	const [cx, cy] = [INNER.w / 2, INNER.h / 2];
	const pos = hubLayout(authors.length, ties, {
		w: INNER.w,
		h: INNER.h,
		padX: MARGIN_X,
		padY: MARGIN_Y
	});
	const hub: NetHub = { x: cx, y: cy, r: HUB_R, label: null };
	const nodes: NetNode[] = authors.map((a, i) => ({
		...pos[i],
		r: R_MIN + (R_MAX - R_MIN) * Math.sqrt(counts[i] / maxCount),
		on: highlight.has(a.semanticId),
		label: null
	}));
	const dirs = nodes.map(({ x, y }) => {
		const len = Math.hypot(x - cx, y - cy) || 1;
		return { ux: (x - cx) / len, uy: (y - cy) / len };
	});

	const bySize = [...nodes.keys()].sort((a, b) => counts[b] - counts[a]);
	const fullNamed = new Set(bySize.slice(0, FULL_NAMES));
	const all: NetHub[] = [hub, ...nodes];
	const circles = all.map((n) => ({ x: n.x - n.r, y: n.y - n.r, w: 2 * n.r, h: 2 * n.r }));
	const order = [...bySize.filter((i) => nodes[i].on), ...bySize.filter((i) => !nodes[i].on)];
	const placing: { node: NetHub; must: boolean; labels: NetLabel[] }[] = [
		{
			node: hub,
			must: true,
			labels: HUB_SPOTS.flatMap(
				(spot) => labelAt(hub, name, spot, HUB_LABEL_MAX, CHAR_W.serif) ?? []
			)
		},
		...order.map((i) => {
			const coauthor = htmlToText(authors[i].name);
			const texts = nodes[i].on
				? [`${coauthor} · ${counts[i]}`, coauthor, lastWord(coauthor)]
				: fullNamed.has(i)
					? [coauthor, lastWord(coauthor)]
					: [lastWord(coauthor)];
			const labels = texts.flatMap((text) =>
				spots(dirs[i]).flatMap((spot) => labelAt(nodes[i], text, spot) ?? [])
			);
			return { node: nodes[i], must: nodes[i].on, labels };
		})
	];
	const picks = placeGreedy(
		placing.map(({ labels, must }) => ({ boxes: labels.map((l) => l.box), must })),
		(k) => circles.filter((_, c) => all[c] !== placing[k].node)
	);
	placing.forEach(({ node, labels }, k) => {
		const pick = picks[k];
		if (pick !== null) node.label = labels[pick];
	});

	const edges: NetEdge[] = ties.map(({ i, j, rate }) => {
		const [a, b] = [nodes[i], nodes[j]];
		return { x1: a.x, y1: a.y, x2: b.x, y2: b.y, rate, on: a.on || b.on };
	});
	edges.sort((a, b) => Number(a.on) - Number(b.on) || a.rate - b.rate);
	return { hub, nodes, edges };
}

// Where a node's label may go, away from the author first.
function spots(dir: { ux: number; uy: number }): Spot[] {
	const side = Math.abs(dir.ux) >= SIDE_DIR ? (Math.sign(dir.ux) as -1 | 1) : 0;
	const first: Spot = { side, up: side === 0 && dir.uy < 0 };
	return [first, ...SPOTS.filter((s) => s.side !== first.side || s.up !== first.up)];
}

// `text` beside (`side` ±1) or above/below (`side` 0) the node, shrunk to fit the card, or null.
function labelAt(
	node: NetHub,
	text: string,
	{ side, up }: Spot,
	max: number = LABEL_MAX,
	charW: number = CHAR_W.sans
): NetLabel | null {
	const x = node.x + side * (node.r + LABEL_GAP);
	const room = side > 0 ? INNER.w - x : side < 0 ? x : 2 * Math.min(x, INNER.w - x);
	const size = labelSize(text, room - 2 * LABEL_PAD, max, charW);
	if (size == null) return null;
	const w = textWidth(text, size, charW);
	const y =
		side !== 0
			? node.y + size * 0.35
			: up
				? node.y - node.r - LABEL_GAP - size * 0.25
				: node.y + node.r + LABEL_GAP + size * 0.8;
	const left = side > 0 ? x : side < 0 ? x - w : x - w / 2;
	const [top, bottom] = [y - size * 0.85, y + size * 0.3];
	if (top < 0 || bottom > INNER.h) return null;
	const box = { x: left - LABEL_PAD, y: top, w: w + 2 * LABEL_PAD, h: bottom - top };
	return { text, x, y, anchor: side > 0 ? 'start' : side < 0 ? 'end' : 'middle', size, box };
}
