import { FULL_HOST, ROOT_TYPES } from './constants';
import { LAST_MOD } from './v_constants';
import type * as tt from '$lib/tree-types';
import * as tf from '$lib/tree-functions';
import * as lf from '$lib/loading-functions';
import oldCountrySem from '$lib/assets/data/old-country-semantic-id-map.json';
import alpha2CC from '$lib/assets/data/country-alpha-2-to-3.json';
import { error, redirect } from '@sveltejs/kit';

export function getExternalUrl(path: string) {
	return `${FULL_HOST}${path}`;
}

export function getSitemapEntry(path: string) {
	return `
	<loc>${getExternalUrl(path)}</loc>
	<lastmod>${LAST_MOD}</lastmod>
`;
}

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

export async function semIdResolver(
	params: { rootType: string; semanticId: string },
	url: URL,
	stem: string,
	fetchFn: typeof fetch = fetch
): Promise<{
	rootType: tt.RootType;
	semanticId: string;
	conf: tt.FullTreeConfig;
	spec: tt.ShareSpec;
	treeSpecs: tt.TreeSpecs;
}> {
	let rootType: tt.RootType;
	if (ROOT_TYPES.includes(params.rootType as tt.RootType)) {
		rootType = params.rootType as tt.RootType;
	} else {
		error(404, 'Not found');
	}
	let semanticId: string = params.semanticId;

	const treeSpecs = await lf.loadSpecs(fetchFn);
	let spec: tt.ShareSpec = tf.parseLinkWithParams(url.searchParams, rootType, treeSpecs);
	let conf: tt.FullTreeConfig = {
		semanticId,
		year: spec.year,
		treeId: spec.treeId,
		rootType,
		wide: false
	};
	let newSemId: string | undefined = semanticId.toLowerCase();
	if (rootType == 'countries') {
		if (semanticId.length == 2) {
			newSemId = (alpha2CC as Record<string, string>)[semanticId.toUpperCase()] || newSemId;
		} else if (semanticId.length != 3) {
			newSemId = (oldCountrySem as Record<string, string>)[semanticId.toLowerCase()];
		}
	}
	if (newSemId == undefined) {
		error(404, 'Not found');
	}
	if (semanticId != newSemId) {
		let linkBase = tf.entToDirectedLink({ rootType, semanticId: newSemId }, stem);
		let link = tf.decorBaseLink(linkBase, conf, spec.selectionState);
		redirect(301, link);
	}
	return { rootType, semanticId, conf, spec, treeSpecs };
}
