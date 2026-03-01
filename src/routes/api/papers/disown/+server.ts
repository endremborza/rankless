import { json } from '@sveltejs/kit';
import type { RequestHandler } from '@sveltejs/kit';
import { PaperDb } from '$lib/server/db';

export const POST: RequestHandler = async ({ locals, request }) => {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	const { wid } = await request.json();
	if (typeof wid !== 'number') return json({ error: 'Invalid wid' }, { status: 400 });
	PaperDb.disownPaper(locals.user.orcid, wid);
	return json({ ok: true });
};

export const DELETE: RequestHandler = async ({ locals, request }) => {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	const { wid } = await request.json();
	if (typeof wid !== 'number') return json({ error: 'Invalid wid' }, { status: 400 });
	PaperDb.unDisownPaper(locals.user.orcid, wid);
	return json({ ok: true });
};
