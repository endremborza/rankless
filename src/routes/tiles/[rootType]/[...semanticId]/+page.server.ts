import type { ViewResult } from '$lib/wire/rankless_server/responses';
import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import * as tf from '$lib/tree-functions';
import { BE_URL } from '$lib/constants';
import { semIdResolver } from '$lib/route-functions';

export const ssr = true;

export const load: PageServerLoad = async ({ params, url, fetch }) => {
	const { conf, treeSpecs } = await semIdResolver(params, url, '/tiles', fetch);

	const view: ViewResult = await fetch(tf.viewBeUrl(BE_URL, conf))
		.then((res) => res.json())
		.then((view) => view)
		.catch(() => error(404, 'Not found'));
	if (view == undefined) {
		error(404, 'Not found');
	}

	if (view) {
		return { view, conf, treeSpecs };
	}

	error(404, 'Not found');
};
