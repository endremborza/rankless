import { ENTITY_SITEMAP_STEP_SIZE, BE_URL } from '$lib/constants';
import { getSitemapIndex } from '$lib/route-functions';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async () => {
	const max_pages: { name: string; count: number }[] = await fetch(`${BE_URL}/counts`)
		.then((r) => r.json())
		.catch(() => []);
	if (!Array.isArray(max_pages)) return getSitemapIndex([]);
	const innards = [];
	for (const { name, count } of max_pages) {
		if (name == 'hit-papers') continue;
		const max_page = Math.floor(count / ENTITY_SITEMAP_STEP_SIZE);
		for (let i = 0; i <= max_page; i++) {
			innards.push(`-entity-${name}-${i + 1}`);
		}
	}
	return getSitemapIndex(innards);
};
