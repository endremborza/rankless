import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { isAdmin } from '$lib/server/admin';
import { LedgerDb } from '$lib/server/db';

export const load: PageServerLoad = ({ locals }) => {
	// 404 (not 403) so the page's existence stays hidden from non-admins.
	if (!isAdmin(locals.user?.orcid)) error(404, 'Not found');
	return { events: LedgerDb.listAllEvents() };
};
