import type { Cookies } from '@sveltejs/kit';

const TEN_YEARS_S = 60 * 60 * 24 * 365 * 10;

// The cookies that each mark the survey answered or dismissed, and the value they are set to.
export const SURVEY_COOKIES = {
	completed: 'survey_completed',
	rejected: 'survey_rejected'
} as const;
export const SURVEY_COOKIE_SET = '1';

type SurveyCookie = (typeof SURVEY_COOKIES)[keyof typeof SURVEY_COOKIES];

// Marks the survey as answered or dismissed so the visitor is not prompted again.
export function setSurveyCookie(cookies: Cookies, name: SurveyCookie) {
	cookies.set(name, SURVEY_COOKIE_SET, { path: '/', maxAge: TEN_YEARS_S, httpOnly: false });
}

export function surveyAnswered(cookies: Cookies): boolean {
	return Object.values(SURVEY_COOKIES).some((name) => cookies.get(name) === SURVEY_COOKIE_SET);
}
