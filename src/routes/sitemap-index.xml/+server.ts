import { SITEMAP_STEP_SIZE } from '$lib/constants';
import { getSitemapIndex } from '$lib/route-functions';
import { getMaxPage } from '$lib/sitemap-functions';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async () => {
	let max_page = await getMaxPage(SITEMAP_STEP_SIZE);
	let innards = [''];
	for (let i = 0; i <= max_page; i++) {
		innards.push(`-${i + 1}`);
	}
	return getSitemapIndex(innards);
};
