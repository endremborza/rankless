import { json } from '@sveltejs/kit';
import type { RequestEvent } from '@sveltejs/kit';
import { LedgerDb } from '$lib/server/db';
import { readManifest } from '$lib/server/manifest';

// Withdraws a pending event. An applied one is immutable: a `revoke` event undoes it.
export function DELETE({ locals, params }: RequestEvent) {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	const event_id = parseInt(params.event_id ?? '');
	if (isNaN(event_id)) return json({ error: 'Invalid event_id' }, { status: 400 });
	const event = LedgerDb.getEvent(event_id);
	if (!event || event.orcid !== locals.user.orcid || event.revoked_at !== null) {
		return json({ error: 'Event not found or already revoked' }, { status: 404 });
	}
	if (readManifest().applied_keys.includes(event.key)) {
		return json({ error: 'Event is applied' }, { status: 409 });
	}
	LedgerDb.revokePending(event_id);
	return json({ ok: true });
}
