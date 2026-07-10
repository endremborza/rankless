import { ORCID_CLIENT_ID, ORCID_CLIENT_SECRET } from '$env/static/private';
import { ORCID_TOKEN_URL, ORCID_REDIRECT_URI, BE_URL } from '$lib/constants';
import type { RequestHandler } from '@sveltejs/kit';
import { setSession, consumeOauthState } from '$lib/server/session';
import { LedgerDb, UserDb } from '$lib/server/db';

export const GET: RequestHandler = async (event) => {
	const code = event.url.searchParams.get('code');
	if (!code) return new Response('Missing code', { status: 400 });

	// CSRF: the callback `state` must match the nonce we set at login time.
	const redirectTo = consumeOauthState(event, event.url.searchParams.get('state'));
	if (redirectTo === null) return new Response('Invalid OAuth state', { status: 400 });

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

	let data: {
		orcid?: string;
		name?: string;
		error?: string;
		error_description?: string;
	};
	try {
		data = await res.json();
	} catch {
		data = {};
	}
	if (!data.orcid) {
		// Log the real reason (invalid_client / redirect_uri_mismatch / expired code, …) so a
		// recurring "Invalid token response" is diagnosable in the FE journal instead of opaque.
		console.error(
			`ORCID token exchange failed: status=${res.status} error=${data.error} desc=${data.error_description}`
		);
		return new Response('Invalid token response', { status: 400 });
	}

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

	const sessionData = { orcid: data.orcid, name: data.name || 'ORCID User', semanticId };
	LedgerDb.pinOwner(data.orcid);
	UserDb.recordLogin(sessionData);
	return setSession(event, sessionData, redirectTo);
};
