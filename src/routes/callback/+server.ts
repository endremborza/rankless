import { ORCID_CLIENT_ID, ORCID_CLIENT_SECRET, } from '$env/static/private';
import { ORCID_TOKEN_URL, ORCID_REDIRECT_URI } from '$lib/constants';
import type { RequestHandler } from '@sveltejs/kit';
import { setSession } from '$lib/server/session';

export const GET: RequestHandler = async ({ url, request }) => {
	const code = url.searchParams.get('code');
	if (!code) return new Response('Missing code', { status: 400 });

	const res = await fetch(ORCID_TOKEN_URL, {
		method: 'POST',
		headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
		body: new URLSearchParams({
			client_id: ORCID_CLIENT_ID,
			client_secret: ORCID_CLIENT_SECRET,
			grant_type: 'authorization_code',
			code,
			redirect_uri: ORCID_REDIRECT_URI
		})
	});

	const data = await res.json();
	if (!data.orcid) return new Response('Invalid token response', { status: 400 });

	// Store orcid ID and access token in cookie
	return setSession({ request } as any, { orcid: data.orcid, name: data.name || 'ORCID User' });
};
