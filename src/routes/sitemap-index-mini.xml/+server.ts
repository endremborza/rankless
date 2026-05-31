import { getSitemapIndex } from '$lib/route-functions';
import { getMaxPage } from '$lib/sitemap-functions';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async () => {
	let max_page = await getMaxPage(200);
	let innards = [''];
	for (let i = 0; i <= Math.min(max_page, 100); i++) {
		innards.push(`-mini-${i + 1}`);
	}
	return getSitemapIndex(innards);
};
