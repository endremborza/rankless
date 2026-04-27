import { ORCID_CLIENT_ID, ORCID_CLIENT_SECRET } from '$env/static/private';
import { ORCID_TOKEN_URL, ORCID_REDIRECT_URI, BE_URL } from '$lib/constants';
import type { RequestHandler } from '@sveltejs/kit';
import { setSession } from '$lib/server/session';
import { LedgerDb } from '$lib/server/db';

export const GET: RequestHandler = async (event) => {
	const code = event.url.searchParams.get('code');
	if (!code) return new Response('Missing code', { status: 400 });

	const redirectTo = event.url.searchParams.get('state') ?? '/';

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

	// Cache semanticId at login time so every page load doesn't need a BE lookup
	let semanticId: string | undefined;
	try {
		const profile = await fetch(`${BE_URL}/orcid/${data.orcid}`).then((r) =>
			r.ok ? r.json() : null
		);
		semanticId = profile?.semanticId;
	} catch {
		// Non-critical — "My Profile" link will be absent until next login
	}

	LedgerDb.pinOwner(data.orcid, 'login');
	return setSession(event, { orcid: data.orcid, name: data.name || 'ORCID User', semanticId }, redirectTo);
};
