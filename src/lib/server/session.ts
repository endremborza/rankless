import type { RequestEvent } from '@sveltejs/kit';

const COOKIE_NAME = 'session';

const COOKIE_OPTS = {
	path: '/',
	httpOnly: true,
	sameSite: 'lax' as const,
	maxAge: 60 * 60 * 24 // 1 day
};

export type SessionUserData = {
	orcid: string;
	name: string;
	semanticId?: string;
};

export function getSession(event: RequestEvent): SessionUserData | null {
	const raw = event.cookies.get(COOKIE_NAME);
	return raw ? JSON.parse(raw) : null;
}

export function setSession(event: RequestEvent, data: SessionUserData, redirectTo = '/'): Response {
	event.cookies.set(COOKIE_NAME, JSON.stringify(data), COOKIE_OPTS);
	return new Response(null, { status: 302, headers: { Location: redirectTo } });
}

export function clearSession(event: RequestEvent): Response {
	event.cookies.delete(COOKIE_NAME, { path: '/' });
	return new Response(null, { status: 302, headers: { Location: '/' } });
}
