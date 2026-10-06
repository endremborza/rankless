import type { EventPayload } from '$lib/wire/rankless_rs/user_ledger';

// Events are referenced across boxes by their logical key `${orcid}|${kind}|${subject_hash}`
// (see logicalKey in ledger-hash.ts), never by the autoincrement event_id — that id is a
// per-box rowid and gets renumbered when DBs are merged (pyscripts/userdb.py).

export type LedgerKind = EventPayload['kind'];

export type ModerationState = 'auto_ok' | 'pending_review' | 'accepted' | 'rejected';

// Client-visible event shape — subset of the full DB row in $lib/server/db.ts. `key` is the
// merge-stable logical id used for all cross-box matching (manifest, revoke targets).
export type LedgerEvent = {
	event_id: number;
	key: string;
	kind: LedgerKind;
	payload: EventPayload;
	revoked_at: string | null;
	moderation: ModerationState;
	created_at: string;
};
