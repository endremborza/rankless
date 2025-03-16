// import "svelte/ssr"
// import "svelte/register"
import type * as tt from '$lib/tree-types';
import * as tf from '$lib/tree-functions';
import type { RequestHandler } from './$types';

import TreeSvg from '$lib/components/TreeSvg.svelte';
import { BE_URL, MAX_LEVEL_COUNT } from '$lib/constants';
// const TreeSvg = require('$lib/components/TreeSvg.svelte').default;

export const GET: RequestHandler = async ({ params, url }) => {
	function updateLevelSpecs(tree: tt.TreeInfo, svgD1: number) {
		let visibleLevelCount = 1;
		for (let meta of (tree.meta || []).slice(2)) {
			if (meta.totalNodes > 0) visibleLevelCount++;
		}
		let topOffset = 0;
		const stepSize = svgD1 / visibleLevelCount;
		for (let i = 0; i < MAX_LEVEL_COUNT; i++) {
			levelOutSpecs[i].totalSize = stepSize;
			levelOutSpecs[i].topOffset = topOffset;
			levelOutSpecs[i].levelOptions = [];
			levelOutSpecs[i].isVisible = i < visibleLevelCount;
			topOffset += levelOutSpecs[i].totalSize;
			if (i == visibleLevelCount - 1) topOffset += svgD1 / 2;
		}
	}

	let rootType = params.rootType as tt.RootType;
	let semanticId = params.semanticId;
	let spec: tt.ShareSpec = tf.parseLinkWithParams(url.searchParams, rootType);
	let conf: tt.FullTreeConfig = { semanticId, year: spec.year, treeId: spec.treeId, rootType };
	const { tree, atts } = await fetch(tf.treeBeUrl(BE_URL, conf, 1))
		.then((res) => res.json())
		.then((resp) => resp);
	const treeSpecs: tt.TreeSpecs = await fetch(`${BE_URL}/specs`)
		.then((res) => res.json())
		.then((specs) => specs);
	const view = await fetch(`${BE_URL}/views/${rootType}/${semanticId}`)
		.then((res) => res.json())
		.then((view) => view);
	let rootName = view.name;

	let treeSpec: tt.TreeSpec = treeSpecs.specs[rootType][conf.treeId];

	let levelOutSpecs: tt.LevelOutSpec[] = tf.getDefaultLevelSpecs();
	let controlSpecs = tf.getDefaultControlSpecs(treeSpec.defaultIsSpec);

	let selectionState: tt.BareNode = spec.selectionState;

	let attributeLabels: tt.AttributeLabels = atts;
	let completeTree: tt.ResponseNode = tree;

	let visibleTreeInfo = tf.deriveVisibleTree(
		completeTree,
		controlSpecs,
		selectionState,
		attributeLabels,
		treeSpec
	);
	// let height = svgD1 * (1 - (headerRate + d1BottomPadRate) / 100);
	let height = 75;
	updateLevelSpecs(visibleTreeInfo, height);
	let props = { selectionState, levelOutSpecs, visibleTreeInfo, attributeLabels, rootName };
	// let component = new TreeSvg({ target: new ShadowRoot() });
	const { html } = TreeSvg.render(props);

	return new Response(html, {
		headers: {
			'Content-Type': 'image/svg+xml',
			'Content-Disposition': 'inline;filename=image.svg'
		}
	});
};
