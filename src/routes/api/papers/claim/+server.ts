import { json } from '@sveltejs/kit';
import type { RequestHandler } from '@sveltejs/kit';
import { PaperDb } from '$lib/server/db';

export const POST: RequestHandler = async ({ locals, request }) => {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	const { doi } = await request.json();
	if (typeof doi !== 'string' || !doi.trim()) return json({ error: 'Invalid doi' }, { status: 400 });
	PaperDb.claimPaper(locals.user.orcid, doi.trim());
	return json({ ok: true });
};

export const DELETE: RequestHandler = async ({ locals, request }) => {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	const { doi } = await request.json();
	if (typeof doi !== 'string' || !doi.trim()) return json({ error: 'Invalid doi' }, { status: 400 });
	PaperDb.unClaimPaper(locals.user.orcid, doi.trim());
	return json({ ok: true });
};
