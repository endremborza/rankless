import { FULL_HOST, LAST_MOD } from '$lib/constants';
import type { RequestHandler } from './$types';

const text = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
  <url>
    <loc>${FULL_HOST}/about</loc>
    <lastmod>${LAST_MOD}</lastmod>
  </url>
</urlset>
`;

export const GET: RequestHandler = () => {
	return new Response(text, { headers: { 'Content-Type': 'application/xml' } });
};
