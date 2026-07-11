import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { isAdmin } from '$lib/server/admin';
import { ConsentDb, LedgerDb, UserDb } from '$lib/server/db';
import type { EmailConsent } from '$lib/types/email-consent';

export const load: PageServerLoad = ({ locals }) => {
	// 404 (not 403) so the page's existence stays hidden from non-admins.
	if (!isAdmin(locals.user?.orcid)) error(404, 'Not found');

	const consents = ConsentDb.listActiveConsents();
	const consentByOrcid = new Map<string, EmailConsent>(consents.map((c) => [c.orcid, c]));
	const users = UserDb.listUsers();
	const seen = new Set(users.map((u) => u.orcid));

	const userRows = users.map((u) => ({ ...u, consent: consentByOrcid.get(u.orcid) ?? null }));
	// Surface anyone who consented but predates the users table (logged in before this
	// feature shipped), so the email list is never silently incomplete.
	for (const c of consents) {
		if (seen.has(c.orcid)) continue;
		userRows.push({
			orcid: c.orcid,
			name: null,
			semantic_id: null,
			first_login_at: c.granted_at,
			last_login_at: c.granted_at,
			login_count: 0,
			consent: c
		});
	}

	return {
		users: userRows,
		pendingCount: LedgerDb.countEventsFiltered({ moderation: 'pending_review' })
	};
};
