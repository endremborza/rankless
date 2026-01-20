import type { RequestEvent } from '@sveltejs/kit';
import { serialize, parse } from 'cookie';

const COOKIE_NAME = 'session';

export function getSession(event: RequestEvent) {
	const cookies = parse(event.request.headers.get('cookie') || '');
	return cookies[COOKIE_NAME] ? JSON.parse(cookies[COOKIE_NAME]) : null;
}

export function setSession(_event: RequestEvent, data: SessionUserData) {
	return new Response(null, {
		status: 302,
		headers: {
			'Set-Cookie': serialize(COOKIE_NAME, JSON.stringify(data), {
				path: '/',
				httpOnly: true,
				sameSite: 'lax',
				maxAge: 60 * 60 * 24 // 1 day
			}),
			Location: '/profile'
		}
	});
}

export function clearSession() {
	return new Response(null, {
		status: 302,
		headers: {
			'Set-Cookie': serialize(COOKIE_NAME, '', {
				path: '/',
				expires: new Date(0)
			}),
			Location: '/'
		}
	});
}

export type SessionUserData = {
	orcid: string;
	name: string
}
