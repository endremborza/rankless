import { error } from '@sveltejs/kit';
import type * as tt from '$lib/tree-types';
import * as tf from '$lib/tree-functions';
import { BE_URL, ROOT_TYPES } from '$lib/constants';
import { loadSpecs } from '$lib/loading-functions';
import { renderSvgComponent } from '$lib/server/render';
import {
	CARD_H,
	CARD_W,
	rasterizeSvg,
	readCardCache,
	writeCardCache
} from '$lib/server/card-raster';
import TreeSvg from '$lib/components/TreeSvg.svelte';

// Shared by the breakdown.svg and breakdown.png endpoints so the SVG build path stays single-sourced.
// Every failure mode is turned into a clean 404 (not a 500): an unknown root type would make
// parseLinkWithParams index undefined, and a backend hiccup / missing entity yields a non-OK or
// malformed response — all of which a crawler may hit with stale or garbage URLs.
export async function buildBreakdownSvg(
	rootType: tt.RootType,
	semanticId: string,
	searchParams: URLSearchParams,
	fetchFn: typeof fetch
): Promise<string> {
	if (!ROOT_TYPES.includes(rootType)) error(404, `unknown entity type: ${rootType}`);
	const treeSpecs = await loadSpecs(fetchFn);
	const spec: tt.ShareSpec = tf.parseLinkWithParams(searchParams, rootType, treeSpecs);
	const conf: tt.FullTreeConfig = {
		semanticId,
		year: spec.year,
		treeId: spec.treeId,
		rootType,
		wide: false
	};
	const [treeRes, viewRes] = await Promise.all([
		fetchFn(tf.treeBeUrl(BE_URL, conf, 1)),
		fetchFn(tf.viewBeUrl(BE_URL, conf))
	]);
	if (!treeRes.ok || !viewRes.ok) error(404, 'breakdown unavailable');
	const parsed = await Promise.all([treeRes.json(), viewRes.json()]).catch(() => null);
	if (!parsed) error(404, 'breakdown unavailable');
	const [treeResp, view] = parsed;
	if (!view?.name || !treeResp?.tree || !treeResp?.atts) error(404, 'breakdown unavailable');

	const treeSpec: tt.TreeSpec = treeSpecs.specs[rootType][conf.treeId];
	const isSpec = searchParams.get('isSpec');
	if (isSpec != null) treeSpec.defaultIsSpec = isSpec === '1';
	const props = {
		selectionState: spec.selectionState,
		treeSpec,
		tree: treeResp.tree,
		attributeLabels: treeResp.atts,
		rootName: view.name,
		height: 100
	};
	return renderSvgComponent(TreeSvg, props);
}

export async function getBreakdownPng(
	rootType: tt.RootType,
	semanticId: string,
	searchParams: URLSearchParams,
	fetchFn: typeof fetch
): Promise<Buffer> {
	const key = cacheKey(rootType, semanticId, searchParams);
	const cached = await readCardCache(key);
	if (cached) return cached;
	const svg = await buildBreakdownSvg(rootType, semanticId, searchParams, fetchFn);
	const png = await rasterizeSvg(svg, CARD_W, CARD_H);
	void writeCardCache(key, png);
	return png;
}

function cacheKey(rootType: string, semanticId: string, searchParams: URLSearchParams): string {
	const params = [...searchParams.entries()]
		.sort(([a], [b]) => a.localeCompare(b))
		.map(([k, v]) => `${k}=${v}`)
		.join('&');
	return `${rootType}/${semanticId}?${params}`;
}
