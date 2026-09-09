import type * as tt from '$lib/tree-types';
import type { RequestHandler } from './$types';
import { getBreakdownPng } from '$lib/server/share-card';

export const GET: RequestHandler = async ({ params, url, fetch }) => {
	const rootType = params.rootType as tt.RootType;
	const png = await getBreakdownPng(rootType, params.semanticId, url.searchParams, fetch);
	const fileSemId = params.semanticId.replaceAll('/', '-');
	return new Response(png, {
		headers: {
			'Content-Type': 'image/png',
			'Content-Disposition': `inline;filename=${fileSemId}-breakdown.png`,
			'Cache-Control': 'public, max-age=86400'
		}
	});
};
