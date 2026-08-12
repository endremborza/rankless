import { json } from '@sveltejs/kit';
import type { RequestEvent } from '@sveltejs/kit';
import { isAdmin } from '$lib/server/admin';
import { runEnrichment } from '$lib/server/review-data';

const DEFAULT_LIMIT = 40;
const MAX_LIMIT = 100;

// Fetches one bounded chunk of missing external metadata for pending events and
// auto-accepts claims the fetched records prove; the client loops while remaining > 0.
export async function POST({ locals, request }: RequestEvent) {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	if (!isAdmin(locals.user.orcid)) return json({ error: 'Forbidden' }, { status: 403 });

	const body = await request.json().catch(() => ({}));
	const limit = Math.min(
		typeof body.limit === 'number' && body.limit > 0 ? body.limit : DEFAULT_LIMIT,
		MAX_LIMIT
	);
	const report = await runEnrichment(limit, body.refresh === true);
	return json({ ok: true, ...report });
}
