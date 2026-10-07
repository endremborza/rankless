import type { RequestHandler } from './$types';
import { appendFile } from 'fs/promises';
import { type SurveyRecord } from '$lib/types';
import { SURVEY_LOG_PATH } from '$lib/paths';
import { setSurveyCookie } from '$lib/server/survey-cookie';

export const POST: RequestHandler = async ({ request, locals, cookies }) => {
	try {
		const data = await request.json();

		const record: SurveyRecord = {
			type: 'submit',
			payload: { ...data, timestamp: new Date().toISOString() },
			userId: locals.user?.orcid ?? null,
			timestamp: new Date().toISOString()
		};

		await appendFile(SURVEY_LOG_PATH, JSON.stringify(record) + '\n', { encoding: 'utf8' });

		setSurveyCookie(cookies, 'survey_completed');

		return new Response(null, { status: 204 });
	} catch (err) {
		console.error('Survey submit error', err);
		return new Response('failed to save', { status: 500 });
	}
};
