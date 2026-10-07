import type { Cookies } from '@sveltejs/kit';

const TEN_YEARS_S = 60 * 60 * 24 * 365 * 10;

// Marks the survey as answered or dismissed so the visitor is not prompted again.
export function setSurveyCookie(cookies: Cookies, name: 'survey_completed' | 'survey_rejected') {
	cookies.set(name, '1', { path: '/', maxAge: TEN_YEARS_S, httpOnly: false });
}
