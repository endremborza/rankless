import { json } from '@sveltejs/kit';
import type { RequestEvent } from '@sveltejs/kit';
import { LedgerDb } from '$lib/server/db';
import type { LedgerPayload } from '$lib/types/ledger';

export function DELETE({ locals, params }: RequestEvent) {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	const event_id = parseInt(params.event_id ?? '');
	if (isNaN(event_id)) return json({ error: 'Invalid event_id' }, { status: 400 });
	const ok = LedgerDb.revokePending(locals.user.orcid, event_id);
	if (!ok) return json({ error: 'Event not found or already revoked' }, { status: 404 });
	return json({ ok: true });
}

export async function PATCH({ locals, params, request }: RequestEvent) {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	const event_id = parseInt(params.event_id ?? '');
	if (isNaN(event_id)) return json({ error: 'Invalid event_id' }, { status: 400 });
	const body = await request.json() as { payload: LedgerPayload };
	if (!body.payload) return json({ error: 'payload required' }, { status: 400 });
	const ok = LedgerDb.editPending(locals.user.orcid, event_id, body.payload);
	if (!ok) return json({ error: 'Event not found, applied, or kind mismatch' }, { status: 404 });
	return json({ ok: true });
}
