import { json } from '@sveltejs/kit';
import type { RequestEvent } from '@sveltejs/kit';
import { ConsentDb } from '$lib/server/db';
import { fetchPublicOrcidEmail } from '$lib/server/enrich';
import {
	PRIVACY_NOTICE_DATE,
	isValidEmail,
	sanitizePurposes,
	type EmailSettings
} from '$lib/types/email-consent';

function settingsOf(orcid: string): EmailSettings | null {
	const consent = ConsentDb.getActiveConsent(orcid);
	return consent && { email: consent.email, purposes: consent.purposes };
}

export async function GET({ locals }: RequestEvent) {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	const { orcid } = locals.user;
	const settings: EmailSettings = settingsOf(orcid) ?? {
		email: await fetchPublicOrcidEmail(orcid).catch((e) => {
			console.error('ORCID public email lookup failed:', e);
			return '';
		}),
		purposes: []
	};
	return json(settings);
}

// Sets the user's whole choice: no purposes withdraws the active consent.
export async function POST({ locals, request }: RequestEvent) {
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	const { orcid } = locals.user;

	const body = await request.json().catch(() => null);
	if (!body || typeof body !== 'object') return json({ error: 'Invalid input' }, { status: 400 });

	const { email: rawEmail, purposes } = body as Record<string, unknown>;
	const email = typeof rawEmail === 'string' ? rawEmail.trim() : '';
	const cleanPurposes = sanitizePurposes(purposes);

	if (cleanPurposes.length === 0) {
		ConsentDb.withdrawConsent(orcid);
		return json({ email, purposes: [] } satisfies EmailSettings);
	}
	if (!isValidEmail(email)) return json({ error: 'Enter a valid email address.' }, { status: 400 });
	ConsentDb.setConsent(orcid, email, cleanPurposes, PRIVACY_NOTICE_DATE);
	return json(settingsOf(orcid));
}
