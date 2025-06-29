import { ENTITY_SITEMAP_STEP_SIZE, BE_URL } from '$lib/constants';
import { getSitemapIndex } from '$lib/route-functions';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async () => {
	let max_pages: { name: string, count: number }[] = await fetch(`${BE_URL}/counts`).then((r) => r.json());
	let innards = [];
	for (const { name, count } of max_pages) {
		let max_page = Math.floor(count / ENTITY_SITEMAP_STEP_SIZE);
		for (let i = 0; i <= max_page; i++) {
			innards.push(`-entity-${name}-${i + 1}`);
		}

	}
	return getSitemapIndex(innards)
};

