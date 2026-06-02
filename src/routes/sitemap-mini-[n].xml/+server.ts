import type { RequestHandler } from './$types';
import { getEntityPath } from '$lib/tree-functions';
import { getSitemapResponse } from '$lib/route-functions';
import { getLinks, respsFromLinks } from '$lib/sitemap-functions';

const STEP_SIZE = 200;

export const GET: RequestHandler = async ({ params }) => {
	const n = parseInt(params.n) - 1;
	const start = n * STEP_SIZE;
	const end = (n + 1) * STEP_SIZE;

	const links = await getLinks(start, end);
	const resps = await respsFromLinks(links);
	const paths = resps.map((e) => getEntityPath(e.rootType, e.semanticId));
	return getSitemapResponse(paths);
};
