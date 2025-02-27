import { BE_URL, SITEMAP_STEP_SIZE, FULL_HOST, LAST_MOD } from '$lib/constants';
import type { SearchResult } from '$lib/tree-types';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async ({ params }) => {
	let n = parseInt(params.n) - 1;
	let start = n * SITEMAP_STEP_SIZE;
	let end = (n + 1) * SITEMAP_STEP_SIZE;

	let links = await fetch(`${BE_URL}/counts`).then((r) =>
		r.json().then((entities) => {
			let out: { url: string; name: string }[] = [];
			entities.forEach((e: { count: number; name: string }) => {
				if (e.count > start) {
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
				l.forEach((e: SearchResult) => resps.push({ ...e, rootType: links[i].name }));
			})
		);
	}

	let innards = resps
		.map(
			(e) => `
  <url>
    <loc>${FULL_HOST}/${e.rootType}/${e.semanticId}</loc>
    <lastmod>${LAST_MOD}</lastmod>
  </url>`
		)
		.join('');

	let text = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
${innards}
</urlset>`;
	return new Response(text, { headers: { 'Content-Type': 'application/xml' } });
};
