import type { EventPayload } from '$lib/wire/rankless_rs/user_ledger';
import { describe, it, expect, vi } from 'vitest';
import type { LedgerEvent } from '$lib/types/ledger';
import {
	createLedgerClient,
	draftBody,
	draftOf,
	emptyDraft,
	parseSemanticId
} from './ledger-client';

const OWN = 'jane-doe';
const TARGET = { event_id: 7 } as LedgerEvent;
const CLAIM = { kind: 'claim_paper', doi: '10.1/x' } as const;

type Call = { method: string; url: string; body: unknown };

// A client over a fake `/api/ledger`: POST answers `posted` (null = refused), DELETE succeeds.
function client(posted: { event_id: number } | null = { event_id: 8 }) {
	const calls: Call[] = [];
	const send = vi.fn(async (url: string, init: RequestInit) => {
		const body = init.body ? JSON.parse(init.body as string) : null;
		calls.push({ method: init.method!, url, body });
		const refused = init.method === 'POST' && body.kind !== 'revoke' && posted === null;
		return { ok: !refused, json: async () => posted } as Response;
	});
	const reload = vi.fn(async () => {});
	return { ledger: createLedgerClient(reload, send as unknown as typeof fetch), calls, reload };
}

describe('replace', () => {
	it('revokes an applied event after posting its replacement', async () => {
		const { ledger, calls } = client();
		expect(await ledger.replace(TARGET, true, CLAIM)).toBe('done');
		expect(calls.map((c) => [c.method, c.body])).toEqual([
			['POST', CLAIM],
			['POST', { kind: 'revoke', target_event_id: TARGET.event_id }]
		]);
	});

	it('withdraws a pending event after posting its replacement', async () => {
		const { ledger, calls } = client();
		expect(await ledger.replace(TARGET, false, CLAIM)).toBe('done');
		expect(calls.map((c) => [c.method, c.url])).toEqual([
			['POST', '/api/ledger'],
			['DELETE', `/api/ledger/${TARGET.event_id}`]
		]);
	});

	it('leaves the event alone when the replacement is refused or names the same subject', async () => {
		const refused = client(null);
		expect(await refused.ledger.replace(TARGET, true, CLAIM)).toBe('failed');
		const same = client({ event_id: TARGET.event_id });
		expect(await same.ledger.replace(TARGET, true, CLAIM)).toBe('unchanged');
		for (const { calls } of [refused, same]) expect(calls).toHaveLength(1);
	});
});

describe('the write queue', () => {
	it('reloads after each write before the next one starts', async () => {
		const { ledger, reload } = client();
		const seen: number[] = [];
		const find = () => {
			seen.push(reload.mock.calls.length);
			return undefined;
		};
		await Promise.all([ledger.post(CLAIM), ledger.withdrawFound(find), ledger.withdrawFound(find)]);
		expect(seen).toEqual([1, 2]);
		expect(reload).toHaveBeenCalledTimes(3);
	});

	it('reports a write that throws as failed and keeps running', async () => {
		const send = vi.fn().mockRejectedValueOnce(new Error('offline'));
		send.mockResolvedValue({ ok: true });
		const ledger = createLedgerClient(async () => {}, send as unknown as typeof fetch);
		expect(await ledger.undo(1)).toBe('failed');
		expect(await ledger.undo(1)).toBe('done');
	});
});

describe('drafts', () => {
	const duplicate = (identifier: string, note = '', prefilled: string | null = null) =>
		({ kind: 'merge_authors', identifier, note, prefilled }) as const;

	it('reads a profile URL or a bare semantic id', () => {
		expect(parseSemanticId(' https://rankless.org/authors/john-doe-2?x=1 ')).toBe('john-doe-2');
		expect(parseSemanticId('/john-doe-2')).toBe('john-doe-2');
	});

	it('makes no request from an empty draft or the owner as their own duplicate', () => {
		expect(draftBody(emptyDraft('claim_paper'), OWN)).toBeNull();
		expect(draftBody(duplicate(`/authors/${OWN}`), OWN)).toBeNull();
		expect(draftBody(duplicate('john-doe-2', ' same lab '), OWN)).toEqual({
			kind: 'merge_authors',
			drop: { semantic_id: 'john-doe-2' },
			note: 'same lab'
		});
		expect(
			draftBody({ kind: 'claim_paper', identifier: ' 10.1/x ', note: '', prefilled: null }, OWN)
		).toEqual(CLAIM);
	});

	const subject = { doi: '10.1/x', semantic_id_at_creation: 'john-doe-2' };
	const of = (payload: unknown) => draftOf(payload as EventPayload);

	it('prefills from the kinds the panel composes only', () => {
		expect(of({ kind: 'claim_paper', work: subject })?.identifier).toBe('10.1/x');
		expect(of({ kind: 'merge_authors', keep: subject, drop: subject, note: 'n' })).toEqual(
			duplicate('john-doe-2', 'n', 'john-doe-2')
		);
		expect(of({ kind: 'disown_paper', work: subject })).toBeNull();
	});

	it('saves a pre-filled draft only once its identifier names another record', () => {
		const report = of({ kind: 'merge_authors', keep: subject, drop: subject, note: 'n' })!;
		for (const identifier of ['john-doe-2', ' /authors/john-doe-2 '])
			expect(draftBody({ ...report, identifier, note: 'other' }, OWN)).toBeNull();
		expect(draftBody({ ...report, identifier: 'john-doe-3' }, OWN)).toEqual({
			kind: 'merge_authors',
			drop: { semantic_id: 'john-doe-3' },
			note: 'n'
		});
		const claim = of({ kind: 'claim_paper', work: subject })!;
		expect(draftBody({ ...claim, identifier: 'https://doi.org/10.1/X' }, OWN)).toBeNull();
		expect(draftBody({ ...claim, identifier: '10.1/y' }, OWN)).toEqual({
			kind: 'claim_paper',
			doi: '10.1/y'
		});
	});
});
