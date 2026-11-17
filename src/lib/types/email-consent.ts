// Opt-in email consent shared between the email block, the consent API, the DB layer, the
// admin view and /privacy. Each grant stores PRIVACY_NOTICE_DATE as its consent version, so
// it records which notice the user agreed to; bump it whenever /privacy materially changes.

export const PRIVACY_NOTICE_DATE = '2026-11-15';

export const EMAIL_PURPOSES = [
	{ key: 'product_updates', label: 'New features' },
	{ key: 'profile_changes', label: 'Changes to my profile' }
] as const;

export type EmailPurposeKey = (typeof EMAIL_PURPOSES)[number]['key'];

export const EMAIL_PURPOSE_KEYS: EmailPurposeKey[] = EMAIL_PURPOSES.map((p) => p.key);

export type EmailConsent = {
	email: string;
	purposes: EmailPurposeKey[];
	consent_version: string;
	granted_at: string;
};

// What the email block shows: the consented address, or else the public ORCID one.
export type EmailSettings = {
	email: string;
	purposes: EmailPurposeKey[];
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
