import { BE_URL, ENTITY_SITEMAP_STEP_SIZE } from '$lib/constants';
import type { RootType, SearchResult } from '$lib/tree-types';
import type { RequestHandler } from './$types';
import { getEntityPath } from '$lib/tree-functions';
import { getSitemapResponse } from '$lib/route-functions';
import { isAsciiOnly } from '$lib/text-format-util';

export const GET: RequestHandler = async ({ params }) => {
	let n = parseInt(params.n) - 1;
	let entity = params.entity as RootType;
	let start = n * ENTITY_SITEMAP_STEP_SIZE;
	let end = (n + 1) * ENTITY_SITEMAP_STEP_SIZE;
	let url = `${BE_URL}/slice/${entity}/${start}/${end}`;
	let resps: string[] = [];
	await fetch(url).then((r) =>
		r.json().then((l) => {
			l.forEach(
				(e: SearchResult) => {
					if (isAsciiOnly(e.semanticId)) {
						resps.push(e.semanticId);
					}
				})
		})
	);
	let paths = resps.map((e) => getEntityPath(entity, e));
	return getSitemapResponse(paths);
};
