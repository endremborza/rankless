import { METHODOLOGY, TREE_SPECS } from '$lib/wire/rankless_server/responses';
import type { AttributeLabels, TreeResponse, TreeSpec } from '$lib/wire/rankless_trees/io';
import { error } from '@sveltejs/kit';
import type * as tt from '$lib/tree-types';
import * as tf from '$lib/tree-functions';
import { BE_URL } from '$lib/constants';
import {
	beJson,
	CARD_SPEC,
	flagParam,
	idsParam,
	intParam,
	LEVEL_WORD,
	type CardContext
} from './kind';

// The entity type at level 1 of the trees each kind reads.
const L1_TYPE = { map: 'countries', fields: 'subfields' } as const;

export type FlatOutCard = {
	levels: tt.LevelT;
	atts: AttributeLabels;
	treeSpec: TreeSpec;
	hl: string[];
	// "this author" and " since 2000" as the caption words them.
	subject: string;
	since: string;
};

// The level-1 weights of a countries or subfields tree the way the entity page's map and concept
// map load them: `tree` (1-based, one with the kind's type at level 1), `since`, `isSpec` (the
// kind's default when it has one, else the tree's) and `hl` (level-1 node ids).
export async function loadFlatOut(
	{ rootType, semanticId, params, fetch }: CardContext,
	kind: keyof typeof L1_TYPE,
	defaultTree: (inds: number[]) => number | undefined,
	defaultYear: number
): Promise<FlatOutCard> {
	const P = CARD_SPEC[kind].params;
	const l1Type = L1_TYPE[kind];
	const rootSpecs = TREE_SPECS.specs[rootType];
	const inds = tf.getTreeIndsByEntityType(rootSpecs)[l1Type];
	const treeId = intParam(params, 'tree', (defaultTree(inds) ?? -1) + 1, 1, rootSpecs.length) - 1;
	if (!inds.includes(treeId)) error(404, `tree has no ${l1Type} level`);
	const year = intParam(
		params,
		'since',
		defaultYear,
		TREE_SPECS.yearBreaks[0],
		METHODOLOGY.workScreen.finalYear
	);
	const base = rootSpecs[treeId];
	const isSpec = 'default' in P.isSpec ? Boolean(P.isSpec.default) : base.defaultIsSpec;
	const treeSpec = { ...base, defaultIsSpec: flagParam(params, 'isSpec', isSpec) };
	const hl = idsParam(params, 'hl', P.hl.max);
	const conf: tt.FullTreeConfig = { semanticId, year, treeId, rootType, wide: true };
	const resp = await beJson<TreeResponse>(fetch, tf.treeBeUrl(BE_URL, conf, 0));
	if (!resp.tree || !resp.atts) error(404, 'card unavailable');
	const levels = tf.flatFromResp(resp, treeSpec.defaultIsSpec, treeSpec);
	if (!levels || Object.keys(levels).length === 0) error(404, 'card unavailable');
	if (hl.some((id) => !(id in levels))) error(404, 'bad hl');
	return {
		levels,
		atts: resp.atts,
		treeSpec,
		hl,
		subject: `this ${LEVEL_WORD[rootType]}`,
		since: tf.hasYearFilter(rootType) ? ` since ${year}` : ''
	};
}
