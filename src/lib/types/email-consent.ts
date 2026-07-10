// Opt-in email consent shared between the consent form, the consent API, the DB
// layer, and the admin view. CONSENT_VERSION is stored with each grant so we have a
// record of which version of the privacy notice the user agreed to; bump it whenever
// the email section of /privacy materially changes.

export const CONSENT_VERSION = '2026-07-01';

export const EMAIL_PURPOSES = [
	{
		key: 'profile_changes',
		label: 'Profile change updates',
		blurb: 'Tell me when the profile corrections I requested are applied.'
	},
	{
		key: 'product_updates',
		label: 'Product updates',
		blurb: 'Occasional news about new Rankless features.'
	},
	{
		key: 'research',
		label: 'Research invitations',
		blurb: 'Invitations to take part in research or short surveys.'
	}
] as const;

export type EmailPurposeKey = (typeof EMAIL_PURPOSES)[number]['key'];

export const EMAIL_PURPOSE_KEYS: EmailPurposeKey[] = EMAIL_PURPOSES.map((p) => p.key);

export type EmailConsent = {
	email: string;
	purposes: EmailPurposeKey[];
	consent_version: string;
	granted_at: string;
};

// Intentionally permissive single-line shape check — real validity is proven by the
// user receiving (and acting on) mail, not by a regex.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function isValidEmail(email: unknown): email is string {
	return typeof email === 'string' && email.length <= 254 && EMAIL_RE.test(email);
}

// Keep only known purpose keys, in canonical order, deduped — never trust the client's
// array shape or ordering.
export function sanitizePurposes(raw: unknown): EmailPurposeKey[] {
	if (!Array.isArray(raw)) return [];
	return EMAIL_PURPOSE_KEYS.filter((k) => raw.includes(k));
}
