import type { LayoutServerLoad } from './$types';
import { isAdmin } from '$lib/server/admin';

export const load: LayoutServerLoad = async ({ locals }) => {
	return {
		user: locals.user,
		isAdmin: isAdmin(locals.user?.orcid)
	};
};
