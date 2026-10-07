import type { RequestHandler } from './$types';
import { appendFile } from 'fs/promises';
import { type SurveyRecord } from '$lib/types';
import { SURVEY_LOG_PATH } from '$lib/paths';
import { setSurveyCookie } from '$lib/server/survey-cookie';

export const POST: RequestHandler = async ({ locals, cookies }) => {
	try {
		const record: SurveyRecord = {
			type: 'reject',
			payload: { reason: 'user_closed' },
			userId: locals.user?.orcid ?? null,
			timestamp: new Date().toISOString()
		};
		await appendFile(SURVEY_LOG_PATH, JSON.stringify(record) + '\n', { encoding: 'utf8' });

		setSurveyCookie(cookies, 'survey_rejected');

		return new Response(null, { status: 204 });
	} catch (err) {
		console.error('Survey reject error', err);
		return new Response('failed', { status: 500 });
	}
};
