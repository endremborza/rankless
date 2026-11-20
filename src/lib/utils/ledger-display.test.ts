import type {
	AppliedManifest,
	AuthorSubject,
	EventPayload,
	WorkSubject
} from '$lib/wire/rankless_rs/user_ledger';
import type { PaperOut } from '$lib/wire/rankless_server/responses';
import { describe, it, expect } from 'vitest';
import type { LedgerEvent } from '$lib/types/ledger';
import { runDate } from '$lib/text-format-util';
import {
	NOT_IN_DATA,
	UNDO_PENDING,
	authorText,
	describeEvent,
	panelRows,
	paperMapOf,
	workText
} from './ledger-display';
import { AWAITING_REVIEW, skippedStatus } from './ledger-status';

const SERVED_RUN = '2026-11-06T18:47:43Z';
const EARLIER_RUN = '2026-09-08T10:00:00Z';
const AS_OF_EARLIER = `as of the release of ${runDate(EARLIER_RUN)}`;

const paper = (oaId: number, name: string, doi = ''): PaperOut =>
	({ oaId, name, doi, wid: oaId % 1000 }) as PaperOut;

const work = (over: Partial<WorkSubject> & { title?: string } = {}): WorkSubject => ({
	oa_id: null,
	doi: null,
	dm_id_at_creation: null,
	semantic_id_at_creation: null,
	run_id_at_creation: null,
	display_snapshot: { title: over.title ?? '', year: null },
	...over
});

const author = (over: Partial<AuthorSubject> & { name?: string } = {}): AuthorSubject => ({
	oa_id: null,
	orcid: null,
	dm_id_at_creation: null,
	semantic_id_at_creation: null,
	run_id_at_creation: null,
	display_snapshot: { display_name: over.name ?? '' },
	...over
});

let nextId = 1;
const event = (payload: EventPayload, over: Partial<LedgerEvent> = {}): LedgerEvent => {
	const event_id = nextId++;
	return {
		event_id,
		key: `orcid|${payload.kind}|${event_id}`,
		kind: payload.kind,
		payload,
		revoked_at: null,
		moderation: 'auto_ok',
		created_at: '',
		...over
	};
};

const manifest = (over: Partial<AppliedManifest> = {}): AppliedManifest => ({
	run_id: SERVED_RUN,
	snapshot_at: SERVED_RUN,
	applied_keys: [],
	skipped: [],
	...over
});

const papers = paperMapOf([
	paper(11, 'Served <i>title</i>', 'https://doi.org/10.1/Served'),
	paper(12, 'No DOI on this one')
]);

describe('workText', () => {
	it('reads the served title by OpenAlex id, then by DOI, over the recorded one', () => {
		const served = { text: '"Served title"', note: null };
		expect(workText(work({ oa_id: 11, title: 'Old title' }), papers, SERVED_RUN)).toEqual(served);
		expect(workText(work({ doi: '10.1/served' }), papers, SERVED_RUN)).toEqual(served);
	});

	it('falls back to the recorded title, dated only when another run recorded it', () => {
		const gone = { oa_id: 99, title: 'Recorded title' };
		expect(
			workText(work({ ...gone, run_id_at_creation: EARLIER_RUN }), papers, SERVED_RUN)
		).toEqual({ text: '"Recorded title"', note: AS_OF_EARLIER });
		for (const run_id_at_creation of [SERVED_RUN, null])
			expect(workText(work({ ...gone, run_id_at_creation }), papers, SERVED_RUN).note).toBeNull();
	});

	it('names an untitled work the data does not hold by its identifier', () => {
		expect(workText(work({ doi: '10.9/absent', oa_id: 99 }), papers, SERVED_RUN)).toEqual({
			text: '10.9/absent',
			note: NOT_IN_DATA
		});
		expect(workText(work({ oa_id: 99 }), papers, SERVED_RUN).text).toBe('W99');
	});
});

describe('authorText', () => {
	it('reads the recorded name, else the ORCID, else the OpenAlex id', () => {
		const named = author({ name: 'Jane Doe', run_id_at_creation: EARLIER_RUN });
		expect(authorText(named, SERVED_RUN)).toEqual({ text: 'Jane Doe', note: AS_OF_EARLIER });
		expect(authorText(author({ orcid: '0000-0001-2345-6789', oa_id: 5 }), SERVED_RUN)).toEqual({
			text: '0000-0001-2345-6789',
			note: NOT_IN_DATA
		});
		expect(authorText(author({ oa_id: 5 }), SERVED_RUN).text).toBe('A5');
	});
});

describe('describeEvent', () => {
	it('describes a revoke by its target and a merge by both papers', () => {
		const merge = event({
			kind: 'merge_papers',
			keep: work({ oa_id: 12 }),
			drop: work({ oa_id: 98, title: 'Preprint', run_id_at_creation: EARLIER_RUN })
		});
		const undo = event({ kind: 'revoke', target_key: merge.key });
		const ctx = { events: [merge, undo], papers, runId: SERVED_RUN };
		expect(describeEvent(merge, ctx)).toEqual({
			text: 'Merged "No DOI on this one" ← "Preprint"',
			note: AS_OF_EARLIER
		});
		expect(describeEvent(undo, ctx).text).toBe('Undo: Merged "No DOI on this one" ← "Preprint"');
		expect(describeEvent(event({ kind: 'revoke', target_key: 'gone' }), ctx).text).toBe(
			'Undo of a previous change'
		);
	});
});

describe('panelRows', () => {
	const claim = (doi: string) => event({ kind: 'claim_paper', work: work({ doi }) });

	it('offers undo on applied events, and change where the panel composes the kind', () => {
		const disown = event({ kind: 'disown_paper', work: work({ oa_id: 11 }) });
		const applied = claim('10.1/served');
		const undone = claim('10.2/undone');
		const undo = event({ kind: 'revoke', target_key: undone.key });
		const rows = panelRows(
			[disown, applied, undone, undo],
			manifest({ applied_keys: [disown.key, applied.key, undone.key] }),
			papers
		);
		expect(rows.applied.map((r) => [r.event, r.actions, r.status, r.undoEventId])).toEqual([
			[disown, ['undo'], null, null],
			[applied, ['undo', 'change'], null, null],
			[undone, ['cancel_undo'], UNDO_PENDING, undo.event_id]
		]);
		expect(rows.pending.map((r) => [r.event, r.actions])).toEqual([[undo, []]]);
	});

	it('lists neither an undo a run has taken in nor the event it undid', () => {
		const undone = claim('10.2/undone');
		const rows = panelRows(
			[undone, event({ kind: 'revoke', target_key: undone.key })],
			manifest(),
			papers
		);
		expect(rows).toEqual({ applied: [], pending: [] });
	});

	it('offers edit only on a composed event the run could not find', () => {
		const orphan = claim('10.9/absent');
		const unattributed = claim('10.1/served');
		const waiting = event(
			{ kind: 'merge_authors', keep: author({ oa_id: 1 }), drop: author({ oa_id: 2 }) },
			{ moderation: 'pending_review' }
		);
		const lostDisown = event({ kind: 'disown_paper', work: work({ oa_id: 99 }) });
		const withdrawn = event(
			{ kind: 'claim_paper', work: work({ doi: '10.3/withdrawn' }) },
			{ revoked_at: '2026-11-01' }
		);
		const rows = panelRows(
			[orphan, unattributed, waiting, lostDisown, withdrawn],
			manifest({
				skipped: [
					{ key: orphan.key, reason: 'doi_not_in_snapshot' },
					{ key: unattributed.key, reason: 'claimant_not_attributed' },
					{ key: lostDisown.key, reason: 'oa_id_not_in_dataset' }
				]
			}),
			papers
		);
		expect(rows.applied).toEqual([]);
		expect(rows.pending.map((r) => [r.event, r.actions, r.status])).toEqual([
			[orphan, ['edit', 'withdraw'], skippedStatus('doi_not_in_snapshot')],
			[unattributed, ['withdraw'], skippedStatus('claimant_not_attributed')],
			[waiting, ['withdraw'], AWAITING_REVIEW],
			[lostDisown, ['withdraw'], skippedStatus('oa_id_not_in_dataset')]
		]);
	});
});
