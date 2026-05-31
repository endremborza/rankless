import { json } from '@sveltejs/kit';
import type { RequestEvent } from '@sveltejs/kit';
import { LedgerDb } from '$lib/server/db';
import { resolveAuthorSubject, ResolveError } from '$lib/server/id_resolver';

export async function POST({ locals, request }: RequestEvent) {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	const body = await request.json();
	const { other_semantic_id, my_semantic_id, note } = body;
	if (typeof other_semantic_id !== 'string' || typeof my_semantic_id !== 'string') {
		return json({ error: 'Invalid input' }, { status: 400 });
	}
	try {
		const [keep, drop] = await Promise.all([
			resolveAuthorSubject({ orcid: locals.user.orcid, semantic_id: my_semantic_id }),
			resolveAuthorSubject({ semantic_id: other_semantic_id })
		]);
		const payload = {
			kind: 'merge_authors' as const,
			keep,
			drop,
			...(note ? { note: String(note) } : {})
		};
		LedgerDb.createEvent(locals.user.orcid, payload);
		return json({ ok: true });
	} catch (e) {
		if (e instanceof ResolveError) return json({ error: e.message }, { status: e.status });
		throw e;
	}
}

export async function DELETE({ locals, request }: RequestEvent) {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	const { other_semantic_id } = await request.json();
	if (typeof other_semantic_id !== 'string')
		return json({ error: 'Invalid input' }, { status: 400 });
	const event_id = LedgerDb.findPendingByPayload(
		locals.user.orcid,
		'merge_authors',
		'$.drop.semantic_id_at_creation',
		other_semantic_id
	);
	if (event_id !== null) LedgerDb.revokePending(locals.user.orcid, event_id);
	return json({ ok: true });
}
