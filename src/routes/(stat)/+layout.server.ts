import type { LayoutServerLoad } from './$types';
import { isAdmin } from '$lib/server/admin';
import { ConsentDb } from '$lib/server/db';
import { EMAIL_FEATURE_ON } from '$lib/constants';
import { loadMethodology } from '$lib/loading-functions';

export const load: LayoutServerLoad = async ({ locals, url, fetch }) => {
	return {
		user: locals.user,
		// Every definition the site explains — the work screen and the hit-paper rule — renders
		// under this layout. Null where the backend is unreachable, so a blip hides the
		// explanations instead of 500ing every page in the group, including the ones that need no
		// backend at all.
		methodology: await loadMethodology(fetch),
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
