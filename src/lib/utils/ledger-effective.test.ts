import type { EventPayload, WorkSubject } from '$lib/wire/rankless_rs/user_ledger';
import { describe, it, expect } from 'vitest';
import type { LedgerEvent } from '$lib/types/ledger';
import { computeEffective, pendingDisown, pendingMerge, withEdits } from './ledger-effective';

const work = (wid: number) => ({ dm_id_at_creation: wid }) as WorkSubject;

let nextId = 1;
const event = (payload: EventPayload, revoked_at: string | null = null): LedgerEvent => {
	const event_id = nextId++;
	const key = `orcid|${payload.kind}|${event_id}`;
	return { event_id, key, kind: payload.kind, payload, revoked_at } as LedgerEvent;
};
const disown = (wid: number, revoked_at: string | null = null) =>
	event({ kind: 'disown_paper', work: work(wid) }, revoked_at);
const undo = (target: LedgerEvent) => event({ kind: 'revoke', target_key: target.key });

describe('computeEffective', () => {
	it('hides what the active disowns and merges name', () => {
		const merge = event({ kind: 'merge_papers', keep: work(3), drop: work(4) });
		const effective = computeEffective([disown(1), disown(2, '2026-11-01'), merge]);
		expect([...effective.disownedWids]).toEqual([1]);
		expect(effective.mergedPairs).toEqual([[3, 4]]);
	});

	it('leaves out an undone event, before and after a run takes the undo in', () => {
		const undone = disown(1);
		expect([...computeEffective([undone, undo(undone)]).disownedWids]).toEqual([]);
	});
});

describe('withEdits', () => {
	it('keeps the edits still in flight over a reload that holds only the first', () => {
		// A three-paper merge and a remove-and-undo: the first merge's reload is in, with the
		// remove written; the rest wait their turn.
		const shown = withEdits(
			[1],
			[[3, 4]],
			[
				{ keep: 3, drop: 5, hidden: true },
				{ keep: 3, drop: 6, hidden: true },
				{ wid: 1, hidden: false },
				{ wid: 2, hidden: true },
				{ wid: 2, hidden: false }
			]
		);
		expect([...shown.disownedWids]).toEqual([]);
		expect(shown.mergedPairs).toEqual([
			[3, 4],
			[3, 5],
			[3, 6]
		]);
	});

	it('shows an unmerged pair and adds a pair once', () => {
		const pairs: [number, number][] = [
			[3, 4],
			[3, 5]
		];
		const shown = withEdits([], pairs, [
			{ keep: 3, drop: 4, hidden: false },
			{ keep: 3, drop: 5, hidden: true }
		]);
		expect(shown.mergedPairs).toEqual([[3, 5]]);
	});
});

describe('the works list finders', () => {
	it('find the active event on the listed work ids', () => {
		const merge = event({ kind: 'merge_papers', keep: work(3), drop: work(4) });
		const events = [disown(1, '2026-11-01'), disown(1), merge];
		expect(pendingDisown(events, 1)).toBe(events[1]);
		expect(pendingDisown(events, 2)).toBeUndefined();
		expect(pendingMerge(events, 3, 4)).toBe(merge);
		expect(pendingMerge(events, 4, 3)).toBeUndefined();
	});
});
