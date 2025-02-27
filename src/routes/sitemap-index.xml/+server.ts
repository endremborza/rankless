import { FULL_HOST, LAST_MOD, SITEMAP_STEP_SIZE, BE_URL } from '$lib/constants';
import type { RequestHandler } from './$types';

function get_sm_entry(suff: string) {
	return `
   <sitemap>
      <loc>${FULL_HOST}/sitemap${suff}.xml</loc>
      <lastmod>${LAST_MOD}</lastmod>
   </sitemap>`;
}

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

	let innards = [];

	max_page = Math.min(10, max_page);

	for (let i = 0; i < max_page; i++) {
		innards.push(get_sm_entry(`-${i + 1}`));
	}

	let text = `<?xml version="1.0" encoding="UTF-8"?>

<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  ${get_sm_entry('')}
  ${innards.join('')}
</sitemapindex>
`;
	return new Response(text, { headers: { 'Content-Type': 'application/xml' } });
};
