import type { EventPayload } from '$lib/wire/rankless_rs/user_ledger';
import type { LedgerEvent, LedgerKind } from '$lib/types/ledger';
import { canonicalDoi } from '$lib/utils/identifiers';

// The kinds the panel composes in a form: each names its subject by one typed identifier.
export type ComposeKind = 'claim_paper' | 'merge_authors';

// What a compose form holds, as typed: a DOI for a claim, a profile for a duplicate, plus the
// note a duplicate report may carry. `prefilled` is the identifier of the event the form
// replaces, null for a new event.
export type ComposeDraft = {
	kind: ComposeKind;
	identifier: string;
	note: string;
	prefilled: string | null;
};

// `unchanged`: nothing was written, since the request names what the log already holds.
export type WriteOutcome = 'done' | 'failed' | 'unchanged';

export type EventBody = { kind: LedgerKind } & Record<string, unknown>;

export type LedgerClient = ReturnType<typeof createLedgerClient>;

export function emptyDraft(kind: ComposeKind): ComposeDraft {
	return { kind, identifier: '', note: '', prefilled: null };
}

// A profile URL or a bare semantic id, as the owner pastes it.
export function parseSemanticId(input: string): string {
	const trimmed = input.trim();
	const match = trimmed.match(/\/authors\/(.+?)(?:\?|$)/);
	return match ? match[1] : trimmed.replace(/^\/+/, '');
}

// The form's values for an event of a composed kind, to correct in place; null for the rest.
export function draftOf(payload: EventPayload): ComposeDraft | null {
	const prefilled = (kind: ComposeKind, identifier: string, note = ''): ComposeDraft => ({
		kind,
		identifier,
		note,
		prefilled: identifier
	});
	switch (payload.kind) {
		case 'claim_paper':
			return prefilled(payload.kind, payload.work.doi ?? '');
		case 'merge_authors':
			return prefilled(
				payload.kind,
				payload.drop.semantic_id_at_creation ?? '',
				payload.note ?? ''
			);
		default:
			return null;
	}
}

// The `/api/ledger` request a draft makes, or null while it names nothing, the owner's own
// profile as its duplicate, or the record the replaced event names. That last is left alone
// rather than looked up again: a profile address can belong to another record by now.
export function draftBody(draft: ComposeDraft, ownSemanticId: string): EventBody | null {
	if (draft.kind === 'claim_paper') {
		const doi = draft.identifier.trim();
		return doi && canonicalDoi(doi) !== draft.prefilled ? { kind: draft.kind, doi } : null;
	}
	const semantic_id = parseSemanticId(draft.identifier);
	if (!semantic_id || semantic_id === ownSemanticId || semantic_id === draft.prefilled) return null;
	const note = draft.note.trim();
	return { kind: draft.kind, drop: { semantic_id }, ...(note ? { note } : {}) };
}

// The browser's writes to `/api/ledger`. They run one at a time, each followed by `reload` (the
// page's data), so a write that reads the page's events sees what the one before it left.
export function createLedgerClient(reload: () => Promise<void>, send: typeof fetch = fetch) {
	let tail: Promise<unknown> = Promise.resolve();

	function queued(write: () => Promise<WriteOutcome>): Promise<WriteOutcome> {
		const written = tail.then(write).catch((): WriteOutcome => 'failed');
		tail = written.then(reload).catch(console.error);
		return tail.then(() => written);
	}

	const post = (body: EventBody) =>
		send('/api/ledger', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(body)
		});
	const withdraw = (event_id: number) => send(`/api/ledger/${event_id}`, { method: 'DELETE' });
	const revoke = (event_id: number) => post({ kind: 'revoke', target_event_id: event_id });
	const outcome = (resp: Response): WriteOutcome => (resp.ok ? 'done' : 'failed');

	return {
		post: (body: EventBody) => queued(async () => outcome(await post(body))),

		// Takes a pending event (or a pending undo) out of the log's active set.
		withdraw: (event_id: number) => queued(async () => outcome(await withdraw(event_id))),

		// `find` runs when the write's turn comes, against the events the page then holds.
		withdrawFound: (find: () => LedgerEvent | undefined) =>
			queued(async (): Promise<WriteOutcome> => {
				const event = find();
				return event ? outcome(await withdraw(event.event_id)) : 'unchanged';
			}),

		// An applied event is immutable: undoing it is a revoke event the next run reads.
		undo: (event_id: number) => queued(async () => outcome(await revoke(event_id))),

		// The replacement first, so a refused one leaves the event as it was; then the event is
		// retired the way its state allows.
		replace: (event: LedgerEvent, applied: boolean, body: EventBody) =>
			queued(async (): Promise<WriteOutcome> => {
				const posted = await post(body);
				if (!posted.ok) return 'failed';
				const { event_id } = (await posted.json()) as { event_id: number };
				if (event_id === event.event_id) return 'unchanged';
				return outcome(await (applied ? revoke : withdraw)(event.event_id));
			})
	};
}
