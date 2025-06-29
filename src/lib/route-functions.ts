import { FULL_HOST } from "./constants";
import { LAST_MOD } from "./v_constants";

export function getExternalUrl(path: string) {
	return `${FULL_HOST}${path}`
}

export function getSitemapEntry(path: string) {
	return `
	<loc>${getExternalUrl(path)}</loc>
	<lastmod>${LAST_MOD}</lastmod>
`}

export function getSubSitemap(suff: string) {
	return `<sitemap>${getSitemapEntry(`/sitemap${suff}.xml`)}</sitemap>`;
}

export function getSitemapUrlSet(paths: string[]) {
	let innards = paths.map((e) => `<url>${getSitemapEntry(e)}</url>`).join('');
	return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">${innards}</urlset>`;
}

export function getSitemapResponse(paths: string[]) {
	return new Response(getSitemapUrlSet(paths), { headers: { 'Content-Type': 'application/xml' } });
}

export function getSitemapIndex(subParams: string[]) {
	let text = `<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${subParams.map(getSubSitemap).join('')}</sitemapindex>`;
	return new Response(text, { headers: { 'Content-Type': 'application/xml' } });

}

