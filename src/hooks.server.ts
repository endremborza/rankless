import type { Handle, HandleFetch } from '@sveltejs/kit';
import { getSession } from '$lib/server/session';

// Tie every server-side fetch to the client's abort signal so a request that
// disconnects mid-render (bots bailing after <head>, nginx->bun upstream
// timeouts) cancels its backend calls instead of leaving bun holding the fetched
// data + render context; one hook covers every route.
export const handleFetch: HandleFetch = ({ event, request, fetch }) =>
	fetch(new Request(request, { signal: event.request.signal }));

export const handle: Handle = async ({ event, resolve }) => {
	event.locals.user = getSession(event);

	const cookies = event.cookies;
	const completed = cookies.get('survey_completed') === '1';
	const rejected = cookies.get('survey_rejected') === '1';
	event.locals.surveyShouldPrompt = !completed && !rejected;
	return resolve(event);
};
