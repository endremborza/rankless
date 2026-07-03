import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { getSession, readFindings } from '$lib/server/mcp-sessions';
import { isAdmin } from '$lib/server/admin';
import { sessionCommand } from '$lib/mcp-util';

export const load: PageServerLoad = ({ params, locals }) => {
	const session = getSession(params.name);
	// 404 (not 403) so a private session's existence stays hidden from non-admins.
	if (!session) error(404, 'Not found');
	if (session.visibility !== 'public' && !isAdmin(locals.user?.orcid)) error(404, 'Not found');
	return {
		session,
		findings: readFindings(params.name),
		command: sessionCommand(session.params)
	};
};
