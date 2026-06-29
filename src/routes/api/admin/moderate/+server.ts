import { json } from '@sveltejs/kit';
import type { RequestEvent } from '@sveltejs/kit';
import { isAdmin } from '$lib/server/admin';
import { LedgerDb } from '$lib/server/db';

export async function POST({ locals, request }: RequestEvent) {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	if (!isAdmin(locals.user.orcid)) return json({ error: 'Forbidden' }, { status: 403 });

	const { event_id, decision } = await request.json();
	if (typeof event_id !== 'number' || (decision !== 'accepted' && decision !== 'rejected')) {
		return json({ error: 'Invalid input' }, { status: 400 });
	}

	const ok = LedgerDb.setModeration(event_id, decision, locals.user.orcid);
	if (!ok) return json({ error: 'Event not found or not pending review' }, { status: 404 });
	return json({ ok: true });
}
