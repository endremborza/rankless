import { error, json } from '@sveltejs/kit';

import type { RequestHandler } from './$types';
import { readJsonBody } from '$lib/server/game-common';
import { parseRun, recordRun, servedSurvivalDeck } from '$lib/server/game-geo';
import type { RunResult } from '$lib/types/game-geo';

// A freshly shuffled survival deck.
export const GET: RequestHandler = async () => {
	const deck = await servedSurvivalDeck();
	if (!deck.length) error(404, 'No cards in the store');
	return json(deck);
};

export const POST: RequestHandler = async ({ request, locals }) => {
	const run = parseRun(await readJsonBody(request));
	if (!run) error(400, 'Bad run payload');
	const standing = recordRun(run, locals.user?.orcid ?? null);
	return json({ standing } satisfies RunResult);
};
