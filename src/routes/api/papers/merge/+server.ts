import { json } from '@sveltejs/kit';
import type { RequestEvent } from '@sveltejs/kit';
import { LedgerDb } from '$lib/server/db';
import { resolveWorkSubject, ResolveError } from '$lib/server/id_resolver';

export async function POST({ locals, request }: RequestEvent) {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	const { wid_keep, wid_drop } = await request.json();
	if (typeof wid_keep !== 'number' || typeof wid_drop !== 'number') {
		return json({ error: 'Invalid input' }, { status: 400 });
	}
	try {
		const [keep, drop] = await Promise.all([
			resolveWorkSubject({ wid: wid_keep }),
			resolveWorkSubject({ wid: wid_drop })
		]);
		LedgerDb.createEvent(locals.user.orcid, { kind: 'merge_papers', keep, drop });
		return json({ ok: true });
	} catch (e) {
		if (e instanceof ResolveError) return json({ error: e.message }, { status: e.status });
		throw e;
	}
}

export async function DELETE({ locals, request }: RequestEvent) {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	const { wid_keep, wid_drop } = await request.json();
	if (typeof wid_keep !== 'number' || typeof wid_drop !== 'number') {
		return json({ error: 'Invalid input' }, { status: 400 });
	}
	const event_id = LedgerDb.findMergePapersPending(locals.user.orcid, wid_keep, wid_drop);
	if (event_id !== null) LedgerDb.revokePending(locals.user.orcid, event_id);
	return json({ ok: true });
}
