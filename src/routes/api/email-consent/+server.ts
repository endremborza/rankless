import { json } from '@sveltejs/kit';
import type { RequestEvent } from '@sveltejs/kit';
import { ConsentDb } from '$lib/server/db';
import { EMAIL_FEATURE_ON } from '$lib/constants';
import { CONSENT_VERSION, isValidEmail, sanitizePurposes } from '$lib/types/email-consent';

function gate(locals: RequestEvent['locals']): Response | null {
	if (!EMAIL_FEATURE_ON) return json({ error: 'Not found' }, { status: 404 });
	if (!locals.user) return json({ error: 'Unauthorized' }, { status: 401 });
	return null;
}

export async function POST({ locals, request }: RequestEvent) {
	const denied = gate(locals);
	if (denied) return denied;

	const body = await request.json().catch(() => null);
	if (!body || typeof body !== 'object') return json({ error: 'Invalid input' }, { status: 400 });

	const { email: rawEmail, purposes } = body as Record<string, unknown>;
	const email = typeof rawEmail === 'string' ? rawEmail.trim() : null;
	if (!isValidEmail(email)) return json({ error: 'Enter a valid email address.' }, { status: 400 });

	const cleanPurposes = sanitizePurposes(purposes);
	if (cleanPurposes.length === 0) {
		return json({ error: 'Pick at least one kind of email.' }, { status: 400 });
	}

	ConsentDb.setConsent(locals.user!.orcid, email, cleanPurposes, CONSENT_VERSION);
	return json({ ok: true, consent: ConsentDb.getActiveConsent(locals.user!.orcid) });
}

export async function DELETE({ locals }: RequestEvent) {
	const denied = gate(locals);
	if (denied) return denied;
	ConsentDb.withdrawConsent(locals.user!.orcid);
	return json({ ok: true });
}
