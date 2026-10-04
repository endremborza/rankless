import { error } from '@sveltejs/kit';
import type * as tt from '$lib/tree-types';
import { BE_URL, FULL_HOST } from '$lib/constants';
import { encodeSemanticId, getEntityPath } from '$lib/tree-functions';
import { loadSpecs } from '$lib/loading-functions';
import { fixViewNames } from '$lib/name-overrides';
import { htmlToText } from '$lib/utils/paper-helpers';
import { renderSvgComponent } from '$lib/server/render';
import { rasterizeSvg, readCardCache, writeCardCache } from '$lib/server/card-raster';
import CardFrame from '$lib/components/cards/CardFrame.svelte';
import { beJson, CARD_SPEC, type CardKind, type CardKindName } from './kind';
import { fields } from './fields';
import { impact } from './impact';
import { map } from './map';
import { network } from './network';
import { papers } from './papers';
import { peers } from './peers';
import { table } from './table';
import { timeline } from './timeline';
import { tree } from './tree';
import { yearly } from './yearly';

// Every card kind by the name in its URL, `/card/<rootType>/<semanticId>/<kind>.png` (the
// semantic id is empty for a cohort card such as the table). A kind is a loader (variant
// parameters → backend calls → props) and a pure-SVG component; the route, the frame, the raster
// and the cache are shared here.
export const CARD_KINDS: Record<CardKindName, CardKind> = {
	tree,
	yearly,
	map,
	fields,
	timeline,
	network,
	papers,
	impact,
	peers,
	table
};

export async function buildCardSvg(
	kind: string,
	rootType: string,
	semanticId: string,
	params: URLSearchParams,
	fetchFn: typeof fetch
): Promise<string> {
	if (!Object.hasOwn(CARD_KINDS, kind)) error(404, 'no such card');
	const card = CARD_KINDS[kind as CardKindName];
	if (!CARD_SPEC[kind as CardKindName].types.includes(rootType)) error(404, 'no such card');
	const rt = rootType as tt.RootType;
	const [specs, view] = await Promise.all([
		loadSpecs(fetchFn),
		semanticId
			? beJson<tt.View>(fetchFn, `${BE_URL}/views/${rt}/${encodeSemanticId(semanticId)}`)
			: null
	]);
	if (view && !view.name) error(404, 'card unavailable');
	if (view) fixViewNames(view);
	const data = await card.load({ rootType: rt, semanticId, params, specs, view, fetch: fetchFn });
	const path = semanticId ? getEntityPath(rt, semanticId) : `/${rt}/table`;
	return renderSvgComponent(CardFrame, {
		name: data.name ?? htmlToText(view?.name ?? ''),
		caption: data.caption,
		url: `${FULL_HOST}${path}`.replace(/^https?:\/\//, ''),
		inner: card.component,
		props: data.props
	});
}

export async function cardPng(
	kind: string,
	rootType: string,
	semanticId: string,
	params: URLSearchParams,
	fetchFn: typeof fetch
): Promise<Buffer> {
	const key = cacheKey(kind, rootType, semanticId, params);
	const cached = await readCardCache(key);
	if (cached) return cached;
	const png = await rasterizeSvg(await buildCardSvg(kind, rootType, semanticId, params, fetchFn));
	void writeCardCache(key, png);
	return png;
}

export function pngResponse(png: Buffer, filename: string): Response {
	return new Response(png, {
		headers: {
			'Content-Type': 'image/png',
			'Content-Disposition': `inline;filename=${filename}.png`,
			'Cache-Control': 'public, max-age=86400'
		}
	});
}

export function svgResponse(svg: string, filename: string): Response {
	return new Response(svg, {
		headers: {
			'Content-Type': 'image/svg+xml',
			'Content-Disposition': `inline;filename=${filename}.svg`
		}
	});
}

function cacheKey(kind: string, rootType: string, semanticId: string, params: URLSearchParams) {
	const query = [...params.entries()]
		.sort(([a], [b]) => a.localeCompare(b))
		.map(([k, v]) => `${k}=${v}`)
		.join('&');
	return `${kind}/${rootType}/${semanticId}?${query}`;
}
