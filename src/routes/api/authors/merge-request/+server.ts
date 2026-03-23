import { json } from '@sveltejs/kit';
import type { RequestEvent } from '@sveltejs/kit';
import { PaperDb } from '$lib/server/db';

export async function POST({ locals, request }: RequestEvent) {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	const body = await request.json();
	const { other_semantic_id, my_semantic_id, note } = body;
	if (typeof other_semantic_id !== 'string' || typeof my_semantic_id !== 'string') {
		return json({ error: 'Invalid input' }, { status: 400 });
	}
	PaperDb.submitAuthorMergeRequest(locals.user.orcid, my_semantic_id, other_semantic_id, note ?? null);
	return json({ ok: true });
}

export async function DELETE({ locals, request }: RequestEvent) {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	const { other_semantic_id } = await request.json();
	if (typeof other_semantic_id !== 'string') return json({ error: 'Invalid input' }, { status: 400 });
	PaperDb.cancelAuthorMergeRequest(locals.user.orcid, other_semantic_id);
	return json({ ok: true });
}
