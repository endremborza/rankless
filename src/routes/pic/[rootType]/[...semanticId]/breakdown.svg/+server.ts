// import "svelte/ssr"
// import "svelte/register"
import type * as tt from '$lib/tree-types';
import * as tf from '$lib/tree-functions';
import type { RequestHandler } from './$types';

import TreeSvg from '$lib/components/TreeSvg.svelte';
import { BE_URL } from '$lib/constants';
import { loadSpecs } from '$lib/loading-functions';
import { renderSvgComponent } from '$lib/server/render';
// const TreeSvg = require('$lib/components/TreeSvg.svelte').default;

export const GET: RequestHandler = async ({ params, url }) => {
	let rootType = params.rootType as tt.RootType;
	let semanticId = params.semanticId;
	const treeSpecs: tt.TreeSpecs = await loadSpecs();
	let spec: tt.ShareSpec = tf.parseLinkWithParams(url.searchParams, rootType, treeSpecs);
	let conf: tt.FullTreeConfig = {
		semanticId,
		year: spec.year,
		treeId: spec.treeId,
		rootType,
		wide: false
	};
	const { tree, atts } = await fetch(tf.treeBeUrl(BE_URL, conf, 1))
		.then((res) => res.json())
		.then((resp) => resp);
	//TODO overkill
	const view = await fetch(tf.viewBeUrl(BE_URL, conf))
		.then((res) => res.json())
		.then((view) => view);
	let rootName = view.name;
	let selectionState: tt.BareNode = spec.selectionState;
	let treeSpec: tt.TreeSpec = treeSpecs.specs[rootType][conf.treeId];

	// let height = svgD1 * (1 - (headerRate + d1BottomPadRate) / 100);
	// let component = new TreeSvg({ target: new ShadowRoot() });
	let props = { selectionState, treeSpec, tree, attributeLabels: atts, rootName, height: 100 };
	const html = renderSvgComponent(TreeSvg, props);
	let urlFriendlySemId = tf.urlFriendlify(conf.semanticId);

	return new Response(html, {
		headers: {
			'Content-Type': 'image/svg+xml',
			'Content-Disposition': `inline;filename=${urlFriendlySemId}-breakdown.svg`
		}
	});
};
