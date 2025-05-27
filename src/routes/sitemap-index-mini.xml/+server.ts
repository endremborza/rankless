import { SITEMAP_STEP_SIZE, BE_URL } from '$lib/constants';
import { getSubSitemap } from '$lib/route-functions';
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
	let innards = [getSubSitemap('')];
	for (let i = 0; i <= Math.min(max_page, 100); i++) {
		innards.push(getSubSitemap(`-mini-${i + 1}`));
	}
	let text = `<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${innards.join('')}</sitemapindex>`;
	return new Response(text, { headers: { 'Content-Type': 'application/xml' } });
};

