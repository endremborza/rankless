import type * as tt from '$lib/tree-types';
import type { RequestHandler } from './$types';
import { buildBreakdownSvg } from '$lib/server/share-card';

export const GET: RequestHandler = async ({ params, url, fetch }) => {
	const rootType = params.rootType as tt.RootType;
	const svg = await buildBreakdownSvg(rootType, params.semanticId, url.searchParams, fetch);
	const fileSemId = params.semanticId.replaceAll('/', '-');
	return new Response(svg, {
		headers: {
			'Content-Type': 'image/svg+xml',
			'Content-Disposition': `inline;filename=${fileSemId}-breakdown.svg`
		}
	});
};
