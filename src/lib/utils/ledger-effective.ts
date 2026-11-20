import type { LedgerEvent } from '$lib/types/ledger';

// The events the owner has undone, by logical key, each with the id of the active revoke that
// names it. An undone event is void whether or not a run has taken the undo in yet.
export function undoEvents(events: LedgerEvent[]): Map<string, number> {
	const undone = new Map<string, number>();
	for (const e of events)
		if (e.payload.kind === 'revoke' && e.revoked_at === null)
			undone.set(e.payload.target_key, e.event_id);
	return undone;
}

export function computeEffective(events: LedgerEvent[]): {
	disownedWids: Set<number>;
	mergedPairs: [number, number][];
} {
	const undone = undoEvents(events);
	const disownedWids = new Set<number>();
	const mergedPairs: [number, number][] = [];

	for (const e of events) {
		if (e.revoked_at !== null || undone.has(e.key)) continue;
		if (e.payload.kind === 'disown_paper') {
			const wid = e.payload.work.dm_id_at_creation;
			if (wid != null) disownedWids.add(wid);
		} else if (e.payload.kind === 'merge_papers') {
			const k = e.payload.keep.dm_id_at_creation;
			const d = e.payload.drop.dm_id_at_creation;
			if (k != null && d != null) mergedPairs.push([k, d]);
		}
	}

	return { disownedWids, mergedPairs };
}

// A works-list change whose write, and the reload after it, has not finished: a remove or a
// merge (`hidden`) or its undo.
export type WorksEdit =
	| { wid: number; hidden: boolean }
	| { keep: number; drop: number; hidden: boolean };

// What the works list hides: the loaded effect with the edits still in flight laid over it in
// the order they were made, since a reload brings in only the writes before it.
export function withEdits(
	disowned: number[],
	merged: [number, number][],
	edits: WorksEdit[]
): { disownedWids: Set<number>; mergedPairs: [number, number][] } {
	const disownedWids = new Set(disowned);
	let mergedPairs = merged;
	for (const edit of edits) {
		if ('wid' in edit) {
			if (edit.hidden) disownedWids.add(edit.wid);
			else disownedWids.delete(edit.wid);
			continue;
		}
		const { keep, drop } = edit;
		mergedPairs = mergedPairs.filter(([k, d]) => !(k === keep && d === drop));
		if (edit.hidden) mergedPairs.push([keep, drop]);
	}
	return { disownedWids, mergedPairs };
}

// The active disown of the work the page lists under `wid`: what the works list's undo withdraws.
export function pendingDisown(events: LedgerEvent[], wid: number): LedgerEvent | undefined {
	return events.find(
		(e) =>
			e.revoked_at === null &&
			e.payload.kind === 'disown_paper' &&
			e.payload.work.dm_id_at_creation === wid
	);
}

export function pendingMerge(
	events: LedgerEvent[],
	keep: number,
	drop: number
): LedgerEvent | undefined {
	return events.find(
		(e) =>
			e.revoked_at === null &&
			e.payload.kind === 'merge_papers' &&
			e.payload.keep.dm_id_at_creation === keep &&
			e.payload.drop.dm_id_at_creation === drop
	);
}
