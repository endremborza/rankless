import { TREE_SPECS } from '$lib/wire/rankless_server/responses';
import type { AttributeLabels, TreeResponse, TreeSpec } from '$lib/wire/rankless_trees/io';
import { error } from '@sveltejs/kit';
import type * as tt from '$lib/tree-types';
import * as tf from '$lib/tree-functions';
import { BE_URL, isEntityType } from '$lib/constants';
import { INNER, LABEL_FLOOR } from '$lib/utils/cards';
import TreeSvg from '$lib/components/TreeSvg.svelte';
import type { LabelStyle } from '$lib/components/QuercusBranches.svelte';
import { beJson, flagParam, LEVEL_WORD, type CardKind } from './kind';

// TreeSvg's viewBox is in units of its `height` and its labels scale a 10-unit base font, so the
// card's label sizes in pixels become scales.
const TREE_HEIGHT = 100;
const LABEL_SCALE = 1 / (INNER.h / TREE_HEIGHT) / 10;
// The largest label, as a multiple of the floor, so the names read as one set.
const LABEL_SPREAD = 1.6;
// The share of the height above the first level; the levels fill the rest.
const TOP_MARGIN = 0.04;
// A band's name is set level within most of its width, between the floor and `LABEL_SPREAD`
// times it, and shortened with an ellipsis while its first word still fits.
const CARD_LABELS: LabelStyle = {
	inset: 0.05,
	widthRate: 0.9,
	fit: {
		minScale: LABEL_FLOOR * LABEL_SCALE,
		maxScale: LABEL_FLOOR * LABEL_SPREAD * LABEL_SCALE,
		truncate: true,
		allowRotation: false
	}
};
// Level 1 draws the bands `paths` opens and the largest others, `BANDS` in all unless `paths` names
// more, the smallest others left out while under `MIN_BAND_SHARE` of the largest `BANDS` and more
// than `MIN_BANDS` remain. Unless `paths` names the opened bands, the largest opens together with
// the next largest whose shown children weigh at least `MIN_BALANCE` times what its own do (or the
// other way round), else alone. Level 2 draws the largest children of the opened bands,
// `MIN_CHILDREN` of each where they fit, else one, else as many as fit, at most `MAX_CHILDREN` in
// all, each at least `MIN_CHILD_SHARE` of the level, so every name fits whole.
const BANDS = 4;
const MIN_BANDS = 3;
const MIN_BAND_SHARE = 0.05;
const MIN_BALANCE = 0.4;
const MIN_CHILDREN = 2;
const MAX_CHILDREN = 6;
const MIN_CHILD_SHARE = 0.1;
const CARD_LAYOUT = { levelsShare: 1 - TOP_MARGIN, childD1Rate: 0.4, labels: CARD_LABELS };

// The entity's citation breakdown, the entity page's own picture: `tree` (1-based), `since`,
// `paths` (level-1 node ids joined by `l`, opened and highlighted) and `isSpec` (band sizes by
// specialization instead of volume) as the page's link carries them.
export const tree: CardKind = {
	component: TreeSvg,
	async load({ rootType, semanticId, params, fetch }) {
		const spec = tf.parseLinkWithParams(params, rootType);
		const conf: tt.FullTreeConfig = {
			semanticId,
			year: spec.year,
			treeId: spec.treeId,
			rootType,
			wide: false
		};
		const resp = await beJson<TreeResponse>(fetch, tf.treeBeUrl(BE_URL, conf, 1));
		if (!resp.tree || !resp.atts) error(404, 'card unavailable');
		const width = (TREE_HEIGHT * INNER.w) / INNER.h;
		const base = TREE_SPECS.specs[rootType][spec.treeId];
		const treeSpec: TreeSpec = {
			...base,
			defaultIsSpec: flagParam(params, 'isSpec', base.defaultIsSpec)
		};
		return {
			props: {
				...CARD_LAYOUT,
				...cardTree(resp.tree, resp.atts, treeSpec, spec.selectionState),
				treeSpec,
				attributeLabels: resp.atts,
				rootName: '',
				height: TREE_HEIGHT,
				width,
				treeD2Offset: 1,
				treeD2: width - 2,
				y: -TREE_HEIGHT * TOP_MARGIN
			},
			caption: treeCaption(rootType, treeSpec, spec.year)
		};
	}
};

type Band = { id: number; weight: number };

// The tree the card draws, cut to its bands and to the children of the opened ones, and which of
// them open, by the size it draws them at (citations or specialization, as `treeSpec` sizes them);
// `given` names the page link's opened bands, those the breakdown lacks ignored.
function cardTree(
	tree: tt.ResponseNode,
	atts: AttributeLabels,
	treeSpec: TreeSpec,
	given: tt.BareNode
): { tree: tt.ResponseNode; controlSpecs: tt.FullControlSpecs; selectionState: tt.BareNode } {
	const isSpec = treeSpec.defaultIsSpec;
	const shown = (l1: number, l2: number, ids: number[]) =>
		tf.deriveVisibleTree(tree, limits(isSpec, l1, l2), opened(ids), atts, treeSpec).tree;
	const childrenOf = (ids: number[]) => {
		const drawn = shown(ids.length, Infinity, ids);
		return ids.map((id) => bySize(drawn.children?.[id]));
	};

	const level1 = bySize(shown(BANDS, 0, []));
	let n = level1.length;
	while (n > MIN_BANDS && level1[n - 1].weight < MIN_BAND_SHARE * weightOf(level1)) n--;
	const givenIds = Object.keys(given.children ?? {})
		.map(Number)
		.filter((id) => tree.children?.[id]);

	const open = (ids: number[], kids: Band[][]) => {
		const others = level1
			.slice(0, n)
			.map((b) => b.id)
			.filter((id) => !ids.includes(id));
		const bands = [...ids, ...others].slice(0, Math.max(BANDS, ids.length));
		return {
			tree: pruned(tree, bands, ids, kids),
			controlSpecs: limits(isSpec, Infinity, Infinity),
			selectionState: opened(ids)
		};
	};
	if (!givenIds.length)
		for (const other of level1.slice(1, n)) {
			const ids = [level1[0].id, other.id];
			const kids = fit(childrenOf(ids), MIN_CHILDREN);
			if (kids && balanced(kids)) return open(ids, kids);
		}
	const ids = givenIds.length ? givenIds : level1.slice(0, 1).map((b) => b.id);
	return open(ids, fitted(childrenOf(ids)));
}

// The default controls, at most `l1` bands on level 1 and `l2` children on each level under it.
function limits(isSpec: boolean, l1: number, l2: number): tt.FullControlSpecs {
	const base = tf.getDefaultControlSpecs(isSpec);
	return {
		...base,
		globalLimit: 0,
		levelSpecs: base.levelSpecs.map((s, i) => ({ ...s, limit: i === 0 ? l1 : l2 }))
	};
}

function opened(ids: number[]): tt.BareNode {
	return { children: Object.fromEntries(ids.map((id) => [id, { children: {} }])) };
}

function bySize(node: tt.EmbeddedNode | undefined): Band[] {
	return Object.entries(node?.children ?? {})
		.map(([id, n]) => ({ id: Number(id), weight: n.weight }))
		.sort((a, b) => b.weight - a.weight);
}

function sum(xs: number[]): number {
	return xs.reduce((a, b) => a + b, 0);
}

function weightOf(bands: Band[]): number {
	return sum(bands.map((b) => b.weight));
}

function fits(level: Band[]): boolean {
	const least = MIN_CHILD_SHARE * weightOf(level);
	return level.every((b) => b.weight >= least);
}

// The first `taken` children of each opened band, joined by the largest next one while the level
// still fits, up to `MAX_CHILDREN` in all.
function grow(kids: Band[][], taken: number[]): Band[][] {
	const level = (t: number[]) => kids.flatMap((k, i) => k.slice(0, t[i]));
	let t = taken;
	while (sum(t) < MAX_CHILDREN) {
		const next = kids
			.map((k, i) => ({ i, kid: k[t[i]] }))
			.filter(({ i, kid }) => kid && fits(level(t.with(i, t[i] + 1))))
			.sort((a, b) => b.kid.weight - a.kid.weight)[0];
		if (!next) break;
		t = t.with(next.i, t[next.i] + 1);
	}
	return kids.map((k, i) => k.slice(0, t[i]));
}

// The largest `least` children of each opened band, grown, or null if a band has fewer or they
// do not fit.
function fit(kids: Band[][], least: number): Band[][] | null {
	const fitsLeast =
		kids.every((k) => k.length >= least) && fits(kids.flatMap((k) => k.slice(0, least)));
	return fitsLeast
		? grow(
				kids,
				kids.map(() => least)
			)
		: null;
}

function fitted(kids: Band[][]): Band[][] {
	return (
		fit(kids, MIN_CHILDREN) ??
		fit(kids, 1) ??
		grow(
			kids,
			kids.map(() => 0)
		)
	);
}

function balanced(kids: Band[][]): boolean {
	const weights = kids.map(weightOf);
	return Math.min(...weights) >= MIN_BALANCE * Math.max(...weights);
}

// `tree` cut to `bands` on level 1, each opened band (`ids`) cut to its `kids`.
function pruned(
	tree: tt.ResponseNode,
	bands: number[],
	ids: number[],
	kids: Band[][]
): tt.ResponseNode {
	const only = (node: tt.ResponseNode, keep: number[]): tt.ResponseNode => ({
		...node,
		children: Object.fromEntries(keep.map((id) => [id, node.children![id]]))
	});
	const cut = only(tree, bands);
	for (const [i, id] of ids.entries())
		cut.children![id] = only(
			cut.children![id],
			kids[i].map((b) => b.id)
		);
	return cut;
}

function treeCaption(rootType: tt.RootType, treeSpec: TreeSpec, year: number): string {
	const levels = treeSpec.breakdowns
		.map((b) => (isEntityType(b.attributeType) ? LEVEL_WORD[b.attributeType] : b.attributeType))
		.join(' › ');
	const since = tf.captionsYear(rootType, year) ? ` of papers since ${year}` : '';
	const sizing = treeSpec.defaultIsSpec ? 'specialization' : 'citation count';
	return `Citations${since} by ${levels} · bands sized by ${sizing}`;
}
