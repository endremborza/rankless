import type * as tt from '$lib/tree-types';
import * as tf from '$lib/tree-functions';
import type { RequestHandler } from './$types';

import TreeSvg from '$lib/components/TreeSvg.svelte';
import { getTopTreeLoader } from '$lib/loading-functions';


export const GET: RequestHandler = async ({ url }) => {
	let loader = await getTopTreeLoader();
	while (loader.conf == undefined) {
		await loader.setRandTree()
	}
	const treeSpecs = loader.treeSpecs;
	let rootType = loader.conf.rootType as tt.RootType;
	let spec: tt.ShareSpec = tf.parseLinkWithParams(url.searchParams, rootType, treeSpecs);
	let selectionState: tt.BareNode = spec.selectionState;
	let props = { selectionState, height: 100, ...loader.getTreeSvgProps() };
	const { html } = TreeSvg.render(props);
	let urlFriendlySemId = tf.urlFriendlify(loader.conf.semanticId)
	return new Response(html, {
		headers: {
			'Content-Type': 'image/svg+xml',
			'Content-Disposition': `inline;filename=${urlFriendlySemId}-breakdown.svg`
		}
	});
};
