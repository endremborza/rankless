import type { TreeResponse, TreeSpec } from '$lib/wire/rankless_trees/io';
import { error } from '@sveltejs/kit';
import type * as tt from '$lib/tree-types';
import * as tf from '$lib/tree-functions';
import { BE_URL, isEntityType } from '$lib/constants';
import { INNER, LABEL_FLOOR } from '$lib/utils/cards';
import TreeSvg from '$lib/components/TreeSvg.svelte';
import { beJson, flagParam, LEVEL_WORD, type CardKind } from './kind';

// TreeSvg's viewBox is in units of its `height` and its labels scale a 10-unit base font, so the
// card's label floor in pixels becomes a scale.
const TREE_HEIGHT = 100;
const MIN_LABEL_SCALE = LABEL_FLOOR / (INNER.h / TREE_HEIGHT) / 10;

// The entity's citation breakdown, the entity page's own picture: `tree` (1-based), `since`,
// `paths` (level-1 node ids joined by `l`, opened and highlighted) and `isSpec` (band sizes by
// specialization instead of volume) as the page's link carries them.
export const tree: CardKind = {
	component: TreeSvg,
	async load({ rootType, semanticId, params, specs, fetch }) {
		const spec = tf.parseLinkWithParams(params, rootType, specs);
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
		const treeSpec: TreeSpec = {
			...specs.specs[rootType][spec.treeId],
			defaultIsSpec: flagParam(params, 'isSpec', specs.specs[rootType][spec.treeId].defaultIsSpec)
		};
		return {
			props: {
				selectionState: spec.selectionState,
				treeSpec,
				tree: resp.tree,
				attributeLabels: resp.atts,
				rootName: '',
				height: TREE_HEIGHT,
				width,
				treeD2Offset: 1,
				treeD2: width - 2,
				y: -TREE_HEIGHT * 0.04,
				minLabelScale: MIN_LABEL_SCALE
			},
			caption: treeCaption(rootType, treeSpec, spec.year)
		};
	}
};

function treeCaption(rootType: tt.RootType, treeSpec: TreeSpec, year: number): string {
	const levels = treeSpec.breakdowns
		.map((b) => (isEntityType(b.attributeType) ? LEVEL_WORD[b.attributeType] : b.attributeType))
		.join(' › ');
	const since = tf.hasYearFilter(rootType) ? ` of papers since ${year}` : '';
	const sizing = treeSpec.defaultIsSpec ? 'specialization' : 'citation count';
	return `Citations${since} by ${levels} · bands sized by ${sizing}`;
}
