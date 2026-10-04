import type { RequestHandler } from './$types';
import { getHomeCardPng } from '$lib/server/cards/home';
import { pngResponse } from '$lib/server/cards';

export const GET: RequestHandler = async ({ fetch }) =>
	pngResponse(await getHomeCardPng(fetch), 'rankless-home');
