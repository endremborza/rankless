import { json } from '@sveltejs/kit';
import type { RequestEvent } from '@sveltejs/kit';
import { LedgerDb } from '$lib/server/db';
import { resolveWorkSubject, ResolveError } from '$lib/server/id_resolver';
import { canonicalDoi } from '$lib/utils/identifiers';

export async function POST({ locals, request }: RequestEvent) {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	const { doi } = await request.json();
	if (typeof doi !== 'string' || !doi.trim())
		return json({ error: 'Invalid input' }, { status: 400 });
	try {
		const work = await resolveWorkSubject({ doi: canonicalDoi(doi) });
		LedgerDb.createEvent(locals.user.orcid, { kind: 'claim_paper', work });
		return json({ ok: true });
	} catch (e) {
		if (e instanceof ResolveError) return json({ error: e.message }, { status: e.status });
		throw e;
	}
}

export async function DELETE({ locals, request }: RequestEvent) {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	const { doi } = await request.json();
	if (typeof doi !== 'string') return json({ error: 'Invalid input' }, { status: 400 });
	const canonical = canonicalDoi(doi);
	const event_id = LedgerDb.findPendingByPayload(
		locals.user.orcid,
		'claim_paper',
		'$.work.doi',
		canonical
	);
	if (event_id !== null) LedgerDb.revokePending(locals.user.orcid, event_id);
	return json({ ok: true });
}
