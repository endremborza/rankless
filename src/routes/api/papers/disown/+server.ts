import { json } from '@sveltejs/kit';
import type { RequestEvent } from '@sveltejs/kit';
import { LedgerDb } from '$lib/server/db';
import { resolveWorkSubject, ResolveError } from '$lib/server/id_resolver';

export async function POST({ locals, request }: RequestEvent) {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	const { wid } = await request.json();
	if (typeof wid !== 'number') return json({ error: 'Invalid input' }, { status: 400 });
	try {
		const work = await resolveWorkSubject({ wid });
		LedgerDb.createEvent(locals.user.orcid, { kind: 'disown_paper', work });
		return json({ ok: true });
	} catch (e) {
		if (e instanceof ResolveError) return json({ error: e.message }, { status: e.status });
		throw e;
	}
}

export async function DELETE({ locals, request }: RequestEvent) {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	const { wid } = await request.json();
	if (typeof wid !== 'number') return json({ error: 'Invalid input' }, { status: 400 });
	const event_id = LedgerDb.findPendingByPayload(
		locals.user.orcid,
		'disown_paper',
		'$.work.dm_id_at_creation',
		wid
	);
	if (event_id !== null) LedgerDb.revokePending(locals.user.orcid, event_id);
	return json({ ok: true });
}
