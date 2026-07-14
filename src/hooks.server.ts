import type { Handle, HandleFetch } from '@sveltejs/kit';
import { getSession } from '$lib/server/session';

// Tie every server-side fetch to the client's abort signal so a request that
// disconnects mid-render (bots bailing after <head>, nginx->bun upstream
// timeouts) cancels its backend calls instead of leaving bun holding the fetched
// data + render context. This was the FE OOM leak; centralising it here covers
// every route (not just the entity page) in one place.
export const handleFetch: HandleFetch = ({ event, request, fetch }) =>
	fetch(new Request(request, { signal: event.request.signal }));

export const handle: Handle = async ({ event, resolve }) => {
	event.locals.user = getSession(event);

	const cookies = event.cookies;
	const completed = cookies.get('survey_completed') === '1';
	// const started = cookies.get('survey_started') === '1';
	const rejected = cookies.get('survey_rejected') === '1';
	const shownThisSession = cookies.get('survey_shown_session') === '1';

	const oneInXShow = 1;
	let shouldPrompt = false;

	if (!completed && !rejected && !shownThisSession) {
		if (Math.random() < 1 / oneInXShow) {
			shouldPrompt = true;
			// set per-session marker so we won't show it again in this session
			// session cookie without maxAge — lasts for browser session
			// cookies.set('survey_shown_session', '1', { path: '/' });
		}
	}
	event.locals.surveyShouldPrompt = shouldPrompt;
	return resolve(event);
};
