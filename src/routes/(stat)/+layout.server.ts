import type { LayoutServerLoad } from './$types';
import { isAdmin } from '$lib/server/admin';
import { ConsentDb } from '$lib/server/db';
import { EMAIL_FEATURE_ON } from '$lib/constants';

export const load: LayoutServerLoad = async ({ locals, url }) => {
	return {
		user: locals.user,
		isAdmin: isAdmin(locals.user?.orcid),
		// drives the header email block: feature on, logged in, nothing on file yet
		askEmail:
			EMAIL_FEATURE_ON &&
			!!locals.user &&
			!url.pathname.startsWith('/email-preferences') &&
			!ConsentDb.getActiveConsent(locals.user.orcid),
		surveyShouldPrompt: locals.surveyShouldPrompt && !url.pathname.startsWith('/survey')
	};
};
