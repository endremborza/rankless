import type { RequestHandler } from './$types';
import { getHomeCardPng } from '$lib/server/share-card';

export const GET: RequestHandler = async ({ fetch }) => {
	const png = await getHomeCardPng(fetch);
	return new Response(png, {
		headers: {
			'Content-Type': 'image/png',
			'Content-Disposition': 'inline;filename=rankless-home.png',
			'Cache-Control': 'public, max-age=86400'
		}
	});
};
