import { BE_URL, SITEMAP_STEP_SIZE } from '$lib/constants';
import type { SearchResult } from '$lib/tree-types';
import type { RequestHandler } from './$types';
import { getEntityPath } from '$lib/tree-functions';
import { getSitemapResponse } from '$lib/route-functions';

function isAsciiOnly(str) {
	return /^[\x01-\x7F]+$/.test(str);
}

export const GET: RequestHandler = async ({ params }) => {
	let n = parseInt(params.n) - 1;
	let start = n * SITEMAP_STEP_SIZE;
	let end = (n + 1) * SITEMAP_STEP_SIZE;

	let links = await fetch(`${BE_URL}/counts`).then((r) =>
		r.json().then((entities) => {
			let out: { url: string; name: string }[] = [];
			entities.forEach((e: { count: number; name: string }) => {
				if (e.count > start && e.name != 'hit-papers') {
					let url = `${BE_URL}/slice/${e.name}/${start}/${end}`;
					out.push({ url, name: e.name });
				}
			});
			return out;
		})
	);

	let resps: SearchResult[] = [];

	for (let i = 0; i < links.length; i++) {
		await fetch(links[i].url).then((r) =>
			r.json().then((l) => {
				l.forEach(
					(e: SearchResult) => {
						if (isAsciiOnly(e.semanticId)) {
							resps.push({ ...e, rootType: links[i].name });
						}
					})
			})
		);
	}
	let paths = resps.map((e) => getEntityPath(e.rootType, e.semanticId));
	return getSitemapResponse(paths);
};
