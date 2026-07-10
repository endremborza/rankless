import { error, redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { ConsentDb } from '$lib/server/db';
import { EMAIL_FEATURE_ON } from '$lib/constants';

export const load: PageServerLoad = ({ locals, url }) => {
	// 404 (not 403) while the feature is unreleased, so the page's existence stays hidden.
	if (!EMAIL_FEATURE_ON) error(404, 'Not found');
	if (!locals.user) redirect(302, `/login?returnTo=${encodeURIComponent('/email-preferences')}`);

	return {
		consent: ConsentDb.getActiveConsent(locals.user.orcid),
		// address the user already typed into the header banner
		prefillEmail: url.searchParams.get('email') ?? ''
	};
};
