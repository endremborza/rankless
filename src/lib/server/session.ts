import type { RequestEvent } from '@sveltejs/kit';
import { randomBytes } from 'crypto';
import { SessionDb } from '$lib/server/db';

const COOKIE_NAME = 'session';
const SESSION_TTL_S = 60 * 60 * 24; // 1 day

const COOKIE_OPTS = {
	path: '/',
	httpOnly: true,
	sameSite: 'lax' as const,
	maxAge: SESSION_TTL_S
};

const OAUTH_STATE_COOKIE = 'oauth_state';
const OAUTH_STATE_OPTS = {
	path: '/',
	httpOnly: true,
	sameSite: 'lax' as const,
	maxAge: 600 // long enough to complete the ORCID round-trip
};

export type SessionUserData = {
	orcid: string;
	name: string;
	semanticId?: string;
};

// Only allow same-origin absolute paths as post-login redirect targets. Rejects
// absolute URLs (`https://evil`), protocol-relative (`//evil`) and backslash
// tricks (`/\evil`) that browsers normalize to off-site navigations.
export function safeReturnTo(raw: string | null | undefined): string {
	if (!raw || !raw.startsWith('/') || raw.startsWith('//') || raw.includes('\\')) return '/';
	return raw;
}

export function getSession(event: RequestEvent): SessionUserData | null {
	const token = event.cookies.get(COOKIE_NAME);
	if (!token) return null;
	const data = SessionDb.get(token);
	if (!data) {
		// stale/expired/forged token — drop it so the browser stops resending
		event.cookies.delete(COOKIE_NAME, { path: '/' });
		return null;
	}
	return data;
}

export function setSession(event: RequestEvent, data: SessionUserData, redirectTo = '/'): Response {
	const token = randomBytes(32).toString('hex');
	SessionDb.create(token, data, SESSION_TTL_S);
	event.cookies.set(COOKIE_NAME, token, COOKIE_OPTS);
	return new Response(null, { status: 302, headers: { Location: safeReturnTo(redirectTo) } });
}

export function clearSession(event: RequestEvent): Response {
	const token = event.cookies.get(COOKIE_NAME);
	if (token) SessionDb.destroy(token);
	event.cookies.delete(COOKIE_NAME, { path: '/' });
	return new Response(null, { status: 302, headers: { Location: '/' } });
}

// Issue a single-use CSRF nonce for the OAuth round-trip and stash it (with the
// validated return path) in a short-lived cookie. Returns the nonce to send as `state`.
export function setOauthState(event: RequestEvent, returnTo: string | null): string {
	const nonce = randomBytes(16).toString('hex');
	event.cookies.set(
		OAUTH_STATE_COOKIE,
		JSON.stringify({ nonce, returnTo: safeReturnTo(returnTo) }),
		OAUTH_STATE_OPTS
	);
	return nonce;
}

// Validate the callback's `state` against the stored nonce and consume the cookie.
// Returns the safe return path on success, or null if the state is missing/mismatched.
export function consumeOauthState(event: RequestEvent, state: string | null): string | null {
	const raw = event.cookies.get(OAUTH_STATE_COOKIE);
	event.cookies.delete(OAUTH_STATE_COOKIE, { path: '/' });
	if (!raw || !state) return null;
	let parsed: { nonce?: string; returnTo?: string };
	try {
		parsed = JSON.parse(raw);
	} catch {
		return null;
	}
	if (!parsed.nonce || parsed.nonce !== state) return null;
	return safeReturnTo(parsed.returnTo);
}
