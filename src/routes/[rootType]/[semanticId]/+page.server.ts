import { error, redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import type * as tt from '$lib/tree-types';
import * as tf from '$lib/tree-functions';
import * as lf from '$lib/loading-functions';
import { BE_URL, FULL_HOST, ROOT_TYPES } from '$lib/constants';

export const load: PageServerLoad = async ({ params, url }) => {
	let rootType: tt.RootType;
	if (ROOT_TYPES.includes(params.rootType as tt.RootType)) {
		rootType = params.rootType as tt.RootType;
	} else {
		error(404, 'Not found');
	}
	let semanticId: string = params.semanticId;

	let spec: tt.ShareSpec = tf.parseLinkWithParams(url.searchParams, rootType);
	let conf: tt.FullTreeConfig = { semanticId, year: spec.year, treeId: spec.treeId, rootType };
	if (semanticId != semanticId.toLowerCase()) {
		//TODO: should be simple thing to test
		let linkBase = tf.entToLink({ rootType, semanticId: semanticId.toLowerCase() });
		let link = tf.decorBaseLink(linkBase, conf, spec.selectionState)
		redirect(301, link);
	}

	const view = await fetch(`${BE_URL}/views/${rootType}/${semanticId}`)
		.then((res) => res.json())
		.then((view) => view)
		.catch(() => error(404, 'Not found'));

	const treeSpecs = await lf.loadSpecs();

	const treeResp: tt.TreeResponse = await fetch(tf.treeBeUrl(BE_URL, conf, 1))
		.then((res) => res.json())
		.then((resp) => resp);
	if (treeResp.tree == undefined || treeResp.shallowed == undefined || treeResp.atts == undefined) {
		error(404, 'Not found');
	}
	const { tree, atts, shallowed } = treeResp;

	let sp = url.searchParams.toString();
	let svgLink = `${FULL_HOST}/pic/${rootType}/${semanticId}/breakdown.svg?${sp}`;

	if (view) {
		return { view, conf, treeSpecs, selectionState: spec.selectionState, tree, atts, svgLink, shallowed };
	}

	error(404, 'Not found');
};

export const ssr = true;
