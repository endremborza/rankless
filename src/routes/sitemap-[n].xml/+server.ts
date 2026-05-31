import { SITEMAP_STEP_SIZE } from '$lib/constants';
import type { RequestHandler } from './$types';
import { getEntityPath } from '$lib/tree-functions';
import { getSitemapResponse } from '$lib/route-functions';
import { respsFromLinks, getLinks } from '$lib/sitemap-functions';

export const GET: RequestHandler = async ({ params }) => {
	let n = parseInt(params.n) - 1;
	let start = n * SITEMAP_STEP_SIZE;
	let end = (n + 1) * SITEMAP_STEP_SIZE;

	let links = await getLinks(start, end);
	let resps = await respsFromLinks(links);
	let paths = resps.map((e) => getEntityPath(e.rootType, e.semanticId));
	return getSitemapResponse(paths);
};
