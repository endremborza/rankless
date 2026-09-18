import { BE_URL, ENTITY_SITEMAP_STEP_SIZE } from '$lib/constants';
import type { RootType } from '$lib/tree-types';
import type { RequestHandler } from './$types';
import { getEntityPath } from '$lib/tree-functions';
import { getSitemapResponse } from '$lib/route-functions';
import { sitemapRows } from '$lib/sitemap-functions';
import { error } from '@sveltejs/kit';

export const GET: RequestHandler = async ({ params }) => {
	const split = params.slug.lastIndexOf('-');
	const n = parseInt(params.slug.slice(split + 1)) - 1;
	if (split < 0 || isNaN(n)) error(404, 'invalid sitemap slug');
	const entity = params.slug.slice(0, split) as RootType;

	const start = n * ENTITY_SITEMAP_STEP_SIZE;
	const end = (n + 1) * ENTITY_SITEMAP_STEP_SIZE;
	const rows = await sitemapRows(`${BE_URL}/slice/${entity}/${start}/${end}`);
	return getSitemapResponse(rows.map((e) => getEntityPath(entity, e.semanticId)));
};
