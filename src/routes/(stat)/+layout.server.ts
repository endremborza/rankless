import type { LayoutServerLoad } from './$types';
import { isAdmin } from '$lib/server/admin';

export const load: LayoutServerLoad = async ({ locals, url }) => {
	return {
		user: locals.user,
		isAdmin: isAdmin(locals.user?.orcid),
		surveyShouldPrompt: locals.surveyShouldPrompt && !url.pathname.startsWith('/survey')
	};
};
