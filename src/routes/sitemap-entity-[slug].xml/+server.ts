import { BE_URL, ENTITY_SITEMAP_STEP_SIZE } from '$lib/constants';
import type { RootType, SearchResult } from '$lib/tree-types';
import type { RequestHandler } from './$types';
import { getEntityPath } from '$lib/tree-functions';
import { getSitemapResponse } from '$lib/route-functions';
import { isAsciiOnly } from '$lib/text-format-util';

export const GET: RequestHandler = async ({ params }) => {
	const n = parseInt(params.n) - 1;
	const entity = params.entity as RootType;
	const start = n * ENTITY_SITEMAP_STEP_SIZE;
	const end = (n + 1) * ENTITY_SITEMAP_STEP_SIZE;
	const url = `${BE_URL}/slice/${entity}/${start}/${end}`;
	const resps: string[] = [];
	await fetch(url).then((r) =>
		r.json().then((l) => {
			l.forEach((e: SearchResult) => {
				if (isAsciiOnly(e.semanticId)) {
					resps.push(e.semanticId);
				}
			});
		})
	);
	const paths = resps.map((e) => getEntityPath(entity, e));
	return getSitemapResponse(paths);
};
