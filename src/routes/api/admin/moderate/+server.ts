import { json } from '@sveltejs/kit';
import type { RequestEvent } from '@sveltejs/kit';
import { isAdmin } from '$lib/server/admin';
import { LedgerDb } from '$lib/server/db';

const MAX_BATCH = 500;

export async function POST({ locals, request }: RequestEvent) {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	if (!isAdmin(locals.user.orcid)) return json({ error: 'Forbidden' }, { status: 403 });

	const body = await request.json();
	const { decision } = body;
	// Bulk shape { event_ids } with the pre-bulk { event_id } form still accepted.
	const ids: unknown = body.event_ids ?? (body.event_id !== undefined ? [body.event_id] : null);
	if (
		!Array.isArray(ids) ||
		ids.length === 0 ||
		ids.length > MAX_BATCH ||
		!ids.every((id) => typeof id === 'number') ||
		(decision !== 'accepted' && decision !== 'rejected')
	) {
		return json({ error: 'Invalid input' }, { status: 400 });
	}

	const updated = LedgerDb.setModerationBulk(ids, decision, locals.user.orcid);
	if (updated.length === 0) {
		return json({ error: 'No event found pending review' }, { status: 404 });
	}
	const updatedSet = new Set(updated);
	return json({ ok: true, updated, skipped: ids.filter((id) => !updatedSet.has(id)) });
}
