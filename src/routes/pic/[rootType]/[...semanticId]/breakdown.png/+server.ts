import type * as tt from '$lib/tree-types';
import * as tf from '$lib/tree-functions';
import type { RequestHandler } from './$types';
import { getBreakdownPng } from '$lib/server/share-card';

export const GET: RequestHandler = async ({ params, url, fetch }) => {
	const rootType = params.rootType as tt.RootType;
	const png = await getBreakdownPng(rootType, params.semanticId, url.searchParams, fetch);
	const urlFriendlySemId = tf.urlFriendlify(params.semanticId);
	return new Response(png, {
		headers: {
			'Content-Type': 'image/png',
			'Content-Disposition': `inline;filename=${urlFriendlySemId}-breakdown.png`,
			'Cache-Control': 'public, max-age=86400'
		}
	});
};
