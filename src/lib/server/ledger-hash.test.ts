import { describe, it, expect } from 'vitest';
import {
	subjectHash,
	workCanonicalKey,
	authorCanonicalKey,
	DEFAULT_MODERATION
} from './ledger-hash';
import type { AuthorSubject, WorkSubject, LedgerPayload } from '$lib/types/ledger';

const emptyDisplay = { title: '', year: null };
const emptyAuthorDisplay = { display_name: '' };

const ws = (oa: number | null, doi: string | null = null): WorkSubject => ({
	oa_id: oa,
	doi,
	dm_id_at_creation: null,
	semantic_id_at_creation: null,
	run_id_at_creation: null,
	display_snapshot: emptyDisplay
});

const as = (oa: number | null, orcid: string | null = null): AuthorSubject => ({
	oa_id: oa,
	orcid,
	dm_id_at_creation: null,
	semantic_id_at_creation: null,
	run_id_at_creation: null,
	display_snapshot: emptyAuthorDisplay
});

describe('canonical keys', () => {
	it('prefers oa_id for works', () => {
		expect(workCanonicalKey(ws(123, '10.1/x'))).toBe('oa:123');
	});
	it('falls back to lowercased doi', () => {
		expect(workCanonicalKey(ws(null, '10.1/Foo'))).toBe('doi:10.1/foo');
	});
	it('throws when work has no stable id', () => {
		expect(() => workCanonicalKey(ws(null, null))).toThrow();
	});
	it('prefers orcid for authors over oa_id', () => {
		expect(authorCanonicalKey(as(99, '0000-0001-2345-6789'))).toBe('orcid:0000-0001-2345-6789');
	});
	it('falls back to oa for authors', () => {
		expect(authorCanonicalKey(as(99, null))).toBe('oa:99');
	});
});

describe('subjectHash determinism and order-invariance', () => {
	it('same disown payload → same hash', () => {
		const p: LedgerPayload = { kind: 'disown_paper', work: ws(42) };
		expect(subjectHash(p)).toBe(subjectHash(p));
	});

	it('merge_papers swap of keep/drop yields the same hash', () => {
		const a: LedgerPayload = { kind: 'merge_papers', keep: ws(10), drop: ws(20) };
		const b: LedgerPayload = { kind: 'merge_papers', keep: ws(20), drop: ws(10) };
		expect(subjectHash(a)).toBe(subjectHash(b));
	});

	it('merge_authors swap of keep/drop yields the same hash', () => {
		const a: LedgerPayload = {
			kind: 'merge_authors',
			keep: as(1, '0000-0001-0000-0001'),
			drop: as(2, '0000-0002-0000-0002')
		};
		const b: LedgerPayload = {
			kind: 'merge_authors',
			keep: as(2, '0000-0002-0000-0002'),
			drop: as(1, '0000-0001-0000-0001')
		};
		expect(subjectHash(a)).toBe(subjectHash(b));
	});

	it('different works → different hash', () => {
		expect(subjectHash({ kind: 'disown_paper', work: ws(1) })).not.toBe(
			subjectHash({ kind: 'disown_paper', work: ws(2) })
		);
	});

	it('disown vs claim of same work hash to the same value (kind disambiguates in dedup)', () => {
		// The unique index includes kind, so equal hash here is fine —
		// kind prevents collision in the table.
		expect(subjectHash({ kind: 'disown_paper', work: ws(7) })).toBe(
			subjectHash({ kind: 'claim_paper', work: ws(7) })
		);
	});

	it('revoke hash depends only on target_event_id', () => {
		const h1 = subjectHash({ kind: 'revoke', target_event_id: 99, reason: 'a' });
		const h2 = subjectHash({ kind: 'revoke', target_event_id: 99, reason: 'b' });
		expect(h1).toBe(h2);
		expect(h1).not.toBe(subjectHash({ kind: 'revoke', target_event_id: 100 }));
	});

	it('doi case is normalized in hash', () => {
		const h1 = subjectHash({ kind: 'claim_paper', work: ws(null, '10.1/Foo') });
		const h2 = subjectHash({ kind: 'claim_paper', work: ws(null, '10.1/foo') });
		expect(h1).toBe(h2);
	});
});

describe('DEFAULT_MODERATION', () => {
	it('disown and merge_papers default to auto_ok', () => {
		expect(DEFAULT_MODERATION.disown_paper).toBe('auto_ok');
		expect(DEFAULT_MODERATION.merge_papers).toBe('auto_ok');
	});
	it('claim and merge_authors require review', () => {
		expect(DEFAULT_MODERATION.claim_paper).toBe('pending_review');
		expect(DEFAULT_MODERATION.merge_authors).toBe('pending_review');
	});
	it('revoke inherits auto_ok by default', () => {
		expect(DEFAULT_MODERATION.revoke).toBe('auto_ok');
	});
});
