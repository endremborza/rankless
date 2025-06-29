import { SITEMAP_STEP_SIZE, BE_URL } from '$lib/constants';
import { getSitemapIndex } from '$lib/route-functions';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async () => {
	let max_page = await fetch(`${BE_URL}/counts`).then((r) =>
		r.json().then((entities) => {
			let max = 0;
			entities.forEach((e: { count: number; name: string }) => {
				let maxPage = Math.floor(e.count / SITEMAP_STEP_SIZE);
				if (maxPage > max) {
					max = maxPage;
				}
			});
			return max;
		})
	);
	let innards = [''];
	for (let i = 0; i <= max_page; i++) {
		innards.push(`-${i + 1}`);
	}
	return getSitemapIndex(innards)
};

