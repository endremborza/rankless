import { getExternalUrl } from '$lib/route-functions';
import type { RequestHandler } from './$types';

const text = `User-agent: *
Allow: /

Sitemap: ${getExternalUrl('/sitemap-index.xml')}
Sitemap: ${getExternalUrl('/sitemap.xml')}`;

export const GET: RequestHandler = () => {
	return new Response(text);
};
