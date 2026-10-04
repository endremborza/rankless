import { error } from '@sveltejs/kit';
import type * as tt from '$lib/tree-types';
import { circleLayout, getIndex } from '$lib/network-util';
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
export type NetNode = { x: number; y: number; r: number; on: boolean; label: NetLabel | null };
export type NetEdge = { x1: number; y1: number; x2: number; y2: number; rate: number; on: boolean };
type Spot = { side: -1 | 0 | 1; up: boolean };

const P = CARD_SPEC.network.params;
const R_MIN = 6;
const R_MAX = 24;
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

// The author's co-author network, the page's picture on a ring: `n` first (ranked) co-authors and
// `with` ones highlighted with their ties.
export const network: CardKind = {
	component: NetworkCard,
	async load({ params, view }) {
		if (!view) error(404, 'no such card');
		const all = view.relations['paper-authors'] ?? [];
		const n = intParam(params, 'n', P.n.default, 2, P.n.max);
		const authors = all.slice(0, n);
		const withIds = idsParam(params, 'with', n);
		if (authors.length < 2) error(404, 'card unavailable');
		if (withIds.some((id) => !authors.some((a) => a.semanticId === id)))
			error(404, 'unknown co-author');
		return {
			props: layoutNetwork(authors, all.length, view.authorNetwork, new Set(withIds)),
			caption: `Co-authors, sized by papers shared with ${htmlToText(view.name)}; ties show the pair's joint papers`
		};
	}
};

// Nodes on an ellipse filling the card in rank order, sized by papers shared with the hero. A
// label goes outside the ring, or beside or across the node when that spot is taken; one with no
// free spot (clear of other nodes and of the labels of highlighted, then bigger, nodes) is left out.
export function layoutNetwork(
	authors: tt.RelatedEntity[],
	total: number,
	weights: number[],
	highlight: Set<string>
): { nodes: NetNode[]; edges: NetEdge[] } {
	const ids = authors.map((a) => a.semanticId);
	const counts = authors.map((a) => a.count ?? 0);
	const maxCount = Math.max(1, ...counts);
	const dirs = circleLayout(ids, weights, { width: 2, height: 2 }).map(({ x, y }) => {
		const len = Math.hypot(x - 1, y - 1) || 1;
		return { ux: (x - 1) / len, uy: (y - 1) / len };
	});
	const rx = INNER.w / 2 - MARGIN_X;
	const ry = INNER.h / 2 - MARGIN_Y;
	const nodes: NetNode[] = authors.map((a, i) => ({
		x: INNER.w / 2 + dirs[i].ux * rx,
		y: INNER.h / 2 + dirs[i].uy * ry,
		r: R_MIN + (R_MAX - R_MIN) * Math.sqrt(counts[i] / maxCount),
		on: highlight.has(a.semanticId),
		label: null
	}));

	const bySize = [...nodes.keys()].sort((a, b) => counts[b] - counts[a]);
	const fullNamed = new Set(bySize.slice(0, FULL_NAMES));
	const circles = nodes.map((n) => ({ x: n.x - n.r, y: n.y - n.r, w: 2 * n.r, h: 2 * n.r }));
	const order = [...bySize.filter((i) => nodes[i].on), ...bySize.filter((i) => !nodes[i].on)];
	const options = order.map((i) => {
		const name = htmlToText(authors[i].name);
		const texts = nodes[i].on
			? [`${name} · ${counts[i]}`, name, lastWord(name)]
			: fullNamed.has(i)
				? [name, lastWord(name)]
				: [lastWord(name)];
		return texts.flatMap((text) =>
			spots(dirs[i]).flatMap((spot) => labelAt(nodes[i], text, spot) ?? [])
		);
	});
	const picks = placeGreedy(
		options.map((labels, k) => ({ boxes: labels.map((l) => l.box), must: nodes[order[k]].on })),
		(k) => circles.filter((_, i) => i !== order[k])
	);
	picks.forEach((pick, k) => {
		if (pick !== null) nodes[order[k]].label = options[k][pick];
	});

	const edges: NetEdge[] = [];
	let maxW = 1;
	for (let i = 0; i < authors.length; i++)
		for (let j = i + 1; j < authors.length; j++) {
			const w = weights[getIndex(i, j, total)] ?? 0;
			if (w <= 0) continue;
			maxW = Math.max(maxW, w);
			const [a, b] = [nodes[i], nodes[j]];
			edges.push({ x1: a.x, y1: a.y, x2: b.x, y2: b.y, rate: w, on: a.on || b.on });
		}
	for (const e of edges) e.rate = Math.sqrt(e.rate / maxW);
	edges.sort((a, b) => Number(a.on) - Number(b.on) || a.rate - b.rate);
	return { nodes, edges };
}

// Where a node's label may go, outward from the ring first.
function spots(dir: { ux: number; uy: number }): Spot[] {
	const side = Math.abs(dir.ux) >= SIDE_DIR ? (Math.sign(dir.ux) as -1 | 1) : 0;
	const first: Spot = { side, up: side === 0 && dir.uy < 0 };
	return [first, ...SPOTS.filter((s) => s.side !== first.side || s.up !== first.up)];
}

// `text` beside (`side` ±1) or above/below (`side` 0) the node, shrunk to fit the card, or null.
function labelAt(node: NetNode, text: string, { side, up }: Spot): NetLabel | null {
	const x = node.x + side * (node.r + LABEL_GAP);
	const room = side > 0 ? INNER.w - x : side < 0 ? x : 2 * Math.min(x, INNER.w - x);
	const size = labelSize(text, room - 2 * LABEL_PAD, LABEL_MAX, CHAR_W.sans);
	if (size == null) return null;
	const w = textWidth(text, size, CHAR_W.sans);
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
