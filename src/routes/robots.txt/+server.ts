import { FULL_HOST } from '$lib/constants';
import type { RequestHandler } from './$types';

const text = `
User-agent: *
Allow: /

Sitemap: ${FULL_HOST}/sitemap-index.xml
Sitemap: ${FULL_HOST}/sitemap.xml`;

export const GET: RequestHandler = () => {
	return new Response(text);
};
