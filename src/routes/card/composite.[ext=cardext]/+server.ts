import type { RequestHandler } from './$types';
import { pngResponse, svgResponse } from '$lib/server/cards';
import { buildComposite, compositePng } from '$lib/server/cards/composite';

export const GET: RequestHandler = async ({ params, url, fetch }) =>
	params.ext === 'svg'
		? svgResponse((await buildComposite(url.searchParams, fetch)).svg, 'composite')
		: pngResponse(await compositePng(url.searchParams, fetch), 'composite');
