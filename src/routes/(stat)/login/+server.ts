import { ORCID_CLIENT_ID } from '$env/static/private';
import { ORCID_REDIRECT_URI, ORCID_AUTH_URL } from '$lib/constants';
import type { RequestHandler } from '@sveltejs/kit';

export const GET: RequestHandler = async ({ url }) => {
	const returnTo = url.searchParams.get('returnTo') ?? '/';
	const params = new URLSearchParams({
		client_id: ORCID_CLIENT_ID,
		response_type: 'code',
		scope: '/authenticate',
		redirect_uri: ORCID_REDIRECT_URI,
		state: returnTo
	});

	return new Response(null, {
		status: 302,
		headers: { Location: `${ORCID_AUTH_URL}?${params.toString()}` }
	});
};
