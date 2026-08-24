import { error, json } from '@sveltejs/kit';

import type { RequestHandler } from './$types';
import { parseResult, practiceCard, recordResult } from '$lib/server/game';

const MAX_BODY_BYTES = 2048;

// Practice card, avoiding the one the player just saw.
export const GET: RequestHandler = ({ url }) => {
	const card = practiceCard(url.searchParams.get('not'));
	if (!card) error(404, 'No cards in the store');
	return json(card);
};

export const POST: RequestHandler = async ({ request, locals }) => {
	const body = await request.text();
	if (body.length > MAX_BODY_BYTES) error(413, 'Result too large');
	let raw: unknown;
	try {
		raw = JSON.parse(body);
	} catch {
		error(400, 'Bad JSON');
	}
	const result = parseResult(raw);
	if (!result) error(400, 'Bad result payload');
	recordResult(result, locals.user?.orcid ?? null);
	return new Response(null, { status: 204 });
};
