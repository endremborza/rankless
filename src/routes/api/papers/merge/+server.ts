import { json } from '@sveltejs/kit';
import type { RequestEvent } from '@sveltejs/kit';
import { PaperDb } from '$lib/server/db';

function extractPair(body: Record<string, unknown>): [number, number] | null {
	const { wid_keep, wid_drop } = body;
	if (typeof wid_keep === 'number' && typeof wid_drop === 'number') return [wid_keep, wid_drop];
	return null;
}

export async function POST(reqEvent: RequestEvent) {
	return mergeMeta(reqEvent, PaperDb.mergePapers)
}

export async function DELETE(reqEvent: RequestEvent) {
	return mergeMeta(reqEvent, PaperDb.unmergePapers)
}


async function mergeMeta({ locals, request }: RequestEvent, fun: (orcid: string, p1: number, p2: number) => void) {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	const pair = extractPair(await request.json());
	if (!pair) return json({ error: 'Invalid input' }, { status: 400 });
	fun(locals.user.orcid, pair[0], pair[1]);
	return json({ ok: true });
}
