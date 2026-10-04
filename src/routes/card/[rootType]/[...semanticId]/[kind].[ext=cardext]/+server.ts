import type { RequestHandler } from './$types';
import { buildCardSvg, cardPng, pngResponse, svgResponse } from '$lib/server/cards';

export const GET: RequestHandler = async ({ params, url, fetch }) => {
	const { rootType, semanticId, kind, ext } = params;
	const filename = `${semanticId.replaceAll('/', '-') || rootType}-${kind}`;
	if (ext === 'svg') {
		return svgResponse(
			await buildCardSvg(kind, rootType, semanticId, url.searchParams, fetch),
			filename
		);
	}
	return pngResponse(await cardPng(kind, rootType, semanticId, url.searchParams, fetch), filename);
};
