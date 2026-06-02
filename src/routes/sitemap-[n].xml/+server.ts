import { SITEMAP_STEP_SIZE } from '$lib/constants';
import type { RequestHandler } from './$types';
import { getEntityPath } from '$lib/tree-functions';
import { getSitemapResponse } from '$lib/route-functions';
import { respsFromLinks, getLinks } from '$lib/sitemap-functions';

export const GET: RequestHandler = async ({ params }) => {
	const n = parseInt(params.n) - 1;
	const start = n * SITEMAP_STEP_SIZE;
	const end = (n + 1) * SITEMAP_STEP_SIZE;

	const links = await getLinks(start, end);
	const resps = await respsFromLinks(links);
	const paths = resps.map((e) => getEntityPath(e.rootType, e.semanticId));
	return getSitemapResponse(paths);
};
