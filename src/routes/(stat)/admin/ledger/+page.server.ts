import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { isAdmin } from '$lib/server/admin';
import { loadReviewQueuePage } from '$lib/server/review-data';
import type { EventFilter } from '$lib/server/db';
import type { LedgerKind, ModerationState } from '$lib/types/ledger';

const STATE_MAP: Record<string, ModerationState | undefined> = {
	pending: 'pending_review',
	accepted: 'accepted',
	rejected: 'rejected',
	auto_ok: 'auto_ok',
	all: undefined
};

const KINDS = new Set<LedgerKind>([
	'claim_paper',
	'disown_paper',
	'merge_papers',
	'merge_authors',
	'revoke',
	'moderation_decision',
	'add_paper_request'
]);

function clampInt(raw: string | null, lo: number, hi: number, dflt: number): number {
	const n = Number(raw);
	if (!Number.isInteger(n)) return dflt;
	return Math.min(Math.max(n, lo), hi);
}

export const load: PageServerLoad = ({ locals, url }) => {
	// 404 (not 403) so the page's existence stays hidden from non-admins.
	if (!isAdmin(locals.user?.orcid)) error(404, 'Not found');

	const stateRaw = url.searchParams.get('state') ?? 'pending';
	const state = stateRaw in STATE_MAP ? stateRaw : 'pending';
	const kindRaw = url.searchParams.get('kind') ?? 'all';
	const kind = KINDS.has(kindRaw as LedgerKind) ? (kindRaw as LedgerKind) : undefined;
	const actor = url.searchParams.get('actor') ?? '';
	const page = clampInt(url.searchParams.get('page'), 1, 1_000_000, 1);
	const per = clampInt(url.searchParams.get('per'), 10, 200, 50);

	const filter: EventFilter = {
		moderation: STATE_MAP[state],
		kind,
		orcid: actor || undefined
	};
	return {
		...loadReviewQueuePage(filter, per, (page - 1) * per),
		me: locals.user!.orcid,
		params: { state, kind: kind ?? 'all', actor, page, per }
	};
};
