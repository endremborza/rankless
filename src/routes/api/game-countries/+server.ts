import { error, json } from '@sveltejs/kit';

import type { RequestHandler } from './$types';
import { readJsonBody } from '$lib/server/game-common';
import { newDeck, parseRun, recordRun } from '$lib/server/game-countries';

// A freshly shuffled practice deck.
export const GET: RequestHandler = async () => {
	const deck = await newDeck();
	if (!deck.length) error(404, 'No cards in the store');
	return json(deck);
};

export const POST: RequestHandler = async ({ request, locals }) => {
	const run = parseRun(await readJsonBody(request));
	if (!run) error(400, 'Bad run payload');
	recordRun(run, locals.user?.orcid ?? null);
	return new Response(null, { status: 204 });
};
