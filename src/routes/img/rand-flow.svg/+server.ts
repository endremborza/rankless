import type * as tt from '$lib/tree-types';
import * as tf from '$lib/tree-functions';
import type { RequestHandler } from './$types';

import TreeSvg from '$lib/components/TreeSvg.svelte';
import { getTopTreeLoader } from '$lib/loading-functions';
import { renderSvgComponent } from '$lib/server/render';

export const GET: RequestHandler = async ({ url }) => {
	const loader = await getTopTreeLoader();
	while (loader.conf == undefined) {
		await loader.setRandTree();
	}
	const treeSpecs = loader.treeSpecs;
	const rootType = loader.conf.rootType as tt.RootType;
	const spec: tt.ShareSpec = tf.parseLinkWithParams(url.searchParams, rootType, treeSpecs);
	const selectionState: tt.BareNode = spec.selectionState;
	const props = { selectionState, height: 100, ...loader.getTreeSvgProps() };
	const html = renderSvgComponent(TreeSvg, props);
	const urlFriendlySemId = tf.urlFriendlify(loader.conf.semanticId);
	return new Response(html, {
		headers: {
			'Content-Type': 'image/svg+xml',
			'Content-Disposition': `inline;filename=${urlFriendlySemId}-breakdown.svg`
		}
	});
};
