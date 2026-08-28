import { redirect } from '@sveltejs/kit';

import type { RequestHandler } from './$types';

// The country game plays at /game-homeground; links to its old address keep
// resolving.
export const GET: RequestHandler = () => {
	redirect(301, '/game-homeground');
};
