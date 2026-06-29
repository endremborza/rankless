import { json } from '@sveltejs/kit';
import type { RequestEvent } from '@sveltejs/kit';
import { LedgerDb } from '$lib/server/db';

export function DELETE({ locals, params }: RequestEvent) {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	const event_id = parseInt(params.event_id ?? '');
	if (isNaN(event_id)) return json({ error: 'Invalid event_id' }, { status: 400 });
	const ok = LedgerDb.revokePending(locals.user.orcid, event_id);
	if (!ok) return json({ error: 'Event not found or already revoked' }, { status: 404 });
	return json({ ok: true });
}
