import { json } from '@sveltejs/kit';
import type { RequestEvent } from '@sveltejs/kit';
import { LedgerDb } from '$lib/server/db';

export async function POST({ locals, params }: RequestEvent) {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	const event_id = parseInt(params.event_id ?? '');
	if (isNaN(event_id)) return json({ error: 'Invalid event_id' }, { status: 400 });

	const target = LedgerDb.getEvent(event_id);
	if (!target || target.orcid !== locals.user.orcid) {
		return json({ error: 'Event not found' }, { status: 404 });
	}

	const ok = LedgerDb.revokePending(locals.user.orcid, event_id);
	if (!ok) return json({ error: 'Event already revoked' }, { status: 409 });
	return json({ ok: true });
}
