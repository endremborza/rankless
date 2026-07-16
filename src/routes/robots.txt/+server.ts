import { getExternalUrl } from '$lib/route-functions';
import crawlers from '$lib/crawlers.json';
import type { RequestHandler } from './$types';

// Crawl-delay is advisory. The enforced half of this policy is the UA-keyed
// limit_req zone that `setup_nginx` (pyscripts/deploy.py) renders from the same
// crawlers.json, so a bot that ignores the delay still gets 429d.
const sitemaps = ['/sitemap-index.xml', '/sitemap-index-entities.xml', '/sitemap.xml'];

const groups = [
	['User-agent: *', 'Allow: /'],
	...crawlers.throttled.map((bot) => [
		`User-agent: ${bot}`,
		'Allow: /',
		`Crawl-delay: ${crawlers.crawlDelaySeconds}`
	])
];

const text = [
	...groups.map((lines) => lines.join('\n')),
	sitemaps.map((s) => `Sitemap: ${getExternalUrl(s)}`).join('\n')
].join('\n\n');

export const GET: RequestHandler = () => {
	return new Response(text);
};
