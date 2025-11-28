import type { RequestHandler } from './$types';
import { appendFile } from 'fs/promises';
import { type SurveyRecord } from '$lib/types';
import { SURVEY_LOG_PATH } from '$lib/constants';

export const POST: RequestHandler = async ({ locals, getClientAddress, cookies }) => {
	try {
		const record: SurveyRecord = {
			type: 'reject',
			payload: { reason: 'user_closed' },
			userId: locals.user?.orcid ?? null,
			ip: getClientAddress?.() ?? null,
			timestamp: new Date().toISOString()
		};
		await appendFile(SURVEY_LOG_PATH, JSON.stringify(record) + '\n', { encoding: 'utf8' });

		cookies.set('survey_rejected', '1', {
			path: '/',
			maxAge: 60 * 60 * 24 * 365 * 10,
			httpOnly: false
		});

		return new Response(null, { status: 204 });
	} catch (err) {
		console.error('Survey reject error', err);
		return new Response('failed', { status: 500 });
	}
};
