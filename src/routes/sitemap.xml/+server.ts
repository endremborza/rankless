import { getSitemapResponse } from '$lib/route-functions';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = () => {
	return getSitemapResponse(['/'])
};
