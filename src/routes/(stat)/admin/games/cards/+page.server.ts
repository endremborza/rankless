import { error, fail } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';
import { isAdmin } from '$lib/server/admin';
import { badgesFor, servedPack, toPlayCard } from '$lib/server/game-geo';
import { listObjects, setObjectStatus } from '$lib/server/objects';
import type { GameFact, StoredCard } from '$lib/types/game-geo';
import type { ObjectStatus } from '$lib/types/objects';
import { KINDS } from '$lib/utils/game-geo';

const STATUSES: ObjectStatus[] = ['new', 'approved', 'rejected'];

export const load: PageServerLoad = async ({ locals }) => {
	// 404 (not 403) so the page's existence stays hidden from non-admins.
	if (!isAdmin(locals.user?.orcid)) error(404, 'Not found');
	// One row per card key: the latest version, which is what a verdict applies
	// to (listObjects orders by obj_key, gen_at DESC).
	const seen = new Set<string>();
	const latest = listObjects({ kinds: KINDS }).filter((o) => {
		const key = `${o.kind}|${o.objKey}`;
		if (seen.has(key)) return false;
		seen.add(key);
		return true;
	});
	// Serving the pack once warms the badge cache for every non-rejected card,
	// so the per-row lookups below mostly resolve without backend calls.
	const served = new Set((await servedPack()).map((c) => `${c.kind}|${c.semId}`));
	const cards = await Promise.all(
		latest.map(async (o) => {
			const stored = o.payload ? ({ kind: o.kind, payload: o.payload } as StoredCard) : null;
			const badges = o.kind === 'country-card' && o.semId ? await badgesFor(o.semId) : [];
			const facts = (stored?.payload.facts ?? []) as GameFact[];
			return {
				id: o.id,
				kind: o.kind,
				semId: o.semId ?? '',
				status: o.status,
				statusNote: o.statusNote,
				card: stored ? toPlayCard(stored, badges) : null,
				facts: { ok: facts.filter((f) => f.ok).length, total: facts.length },
				served: served.has(`${o.kind}|${o.semId}`)
			};
		})
	);
	return {
		cards: cards.sort(
			(a, b) =>
				a.kind.localeCompare(b.kind) ||
				(a.card?.name ?? a.semId).localeCompare(b.card?.name ?? b.semId)
		)
	};
};

export const actions: Actions = {
	review: async ({ request, locals }) => {
		if (!isAdmin(locals.user?.orcid)) error(403, 'Admins only');
		const form = await request.formData();
		const id = Number(form.get('id'));
		const status = String(form.get('status')) as ObjectStatus;
		const note = String(form.get('note') ?? '').trim() || null;
		if (!Number.isInteger(id) || !STATUSES.includes(status))
			return fail(400, { message: 'Bad review input.' });
		if (status === 'rejected' && !note)
			return fail(400, { message: 'Rejecting needs a reason (kept for later review).' });
		if (!setObjectStatus(id, status, note)) return fail(404, { message: 'No such card.' });
		return { reviewed: id };
	}
};
