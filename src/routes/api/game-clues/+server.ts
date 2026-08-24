import { error, json } from '@sveltejs/kit';

import type { RequestHandler } from './$types';
import { readJsonBody } from '$lib/server/game-common';
import { parseResult, practiceCard, recordResult } from '$lib/server/game-clues';

// Practice card, avoiding the one the player just saw.
export const GET: RequestHandler = ({ url }) => {
	const card = practiceCard(url.searchParams.get('not'));
	if (!card) error(404, 'No cards in the store');
	return json(card);
};

export const POST: RequestHandler = async ({ request, locals }) => {
	const result = parseResult(await readJsonBody(request));
	if (!result) error(400, 'Bad result payload');
	recordResult(result, locals.user?.orcid ?? null);
	return new Response(null, { status: 204 });
};
