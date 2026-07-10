import { describe, it, expect } from 'vitest';
import { isValidEmail, sanitizePurposes, EMAIL_PURPOSE_KEYS } from './email-consent';

describe('isValidEmail', () => {
	it('accepts a normal address', () => {
		expect(isValidEmail('jane.doe@uni-corvinus.hu')).toBe(true);
	});

	it('rejects malformed or non-string values', () => {
		expect(isValidEmail('nope')).toBe(false);
		expect(isValidEmail('a@b')).toBe(false);
		expect(isValidEmail('a @b.com')).toBe(false);
		expect(isValidEmail('')).toBe(false);
		expect(isValidEmail(null)).toBe(false);
		expect(isValidEmail(123)).toBe(false);
	});

	it('rejects overly long addresses', () => {
		expect(isValidEmail('a'.repeat(250) + '@b.com')).toBe(false);
	});
});

describe('sanitizePurposes', () => {
	it('keeps only known keys, in canonical order, deduped', () => {
		const out = sanitizePurposes(['research', 'bogus', 'profile_changes', 'research']);
		expect(out).toEqual(['profile_changes', 'research']);
	});

	it('returns [] for non-array input', () => {
		expect(sanitizePurposes('research')).toEqual([]);
		expect(sanitizePurposes(null)).toEqual([]);
		expect(sanitizePurposes(undefined)).toEqual([]);
	});

	it('normalizes to canonical order regardless of input order', () => {
		const out = sanitizePurposes([...EMAIL_PURPOSE_KEYS].reverse());
		expect(out).toEqual(EMAIL_PURPOSE_KEYS);
	});
});
