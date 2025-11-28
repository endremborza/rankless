import type { RequestHandler } from './$types';
import { appendFile } from 'fs/promises';
import { type SurveyRecord } from '$lib/types';
import { SURVEY_LOG_PATH } from '$lib/constants';


export const POST: RequestHandler = async ({ request, locals, getClientAddress, cookies }) => {
	try {
		const data = await request.json();

		const record: SurveyRecord = {
			type: 'submit',
			payload: { ...data, timestamp: new Date().toISOString() },
			userId: locals.user?.orcid ?? null,
			ip: getClientAddress?.() ?? null,
			timestamp: new Date().toISOString()
		};

		await appendFile(SURVEY_LOG_PATH, JSON.stringify(record) + '\n', { encoding: 'utf8' });

		// set cookie so they won't be prompted again
		cookies.set('survey_completed', '1', {
			path: '/',
			// 10 years
			maxAge: 60 * 60 * 24 * 365 * 10,
			httpOnly: false // allow client-side reading if you want; security trade-off
		});

		return new Response(null, { status: 204 });
	} catch (err) {
		console.error('Survey submit error', err);
		return new Response('failed to save', { status: 500 });
	}
};
