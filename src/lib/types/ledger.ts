// Cross-language type boundaries:
//
// active.jsonl (TS → Rust): WorkSubject, AuthorSubject, LedgerKind, LedgerPayload
//   Mirror: rankless_rs/src/user_ledger.rs — EventPayload, WorkSubject, AuthorSubject
//
// applied_manifest.json (Rust → TS): AppliedManifest
//   Mirror of: rankless_rs/src/user_ledger.rs — write_final_manifest output

export type WorkSubject = {
	oa_id: number | null;
	doi: string | null;
	dm_id_at_creation: number | null;
	semantic_id_at_creation: string | null;
	run_id_at_creation: string | null;
	display_snapshot: { title: string; year: number | null };
};

export type AuthorSubject = {
	oa_id: number | null;
	orcid: string | null;
	dm_id_at_creation: number | null;
	semantic_id_at_creation: string | null;
	run_id_at_creation: string | null;
	display_snapshot: { display_name: string };
};

export type LedgerKind =
	| 'disown_paper'
	| 'claim_paper'
	| 'merge_papers'
	| 'merge_authors'
	| 'revoke'
	| 'moderation_decision'
	| 'add_paper_request';

export type ModerationState = 'auto_ok' | 'pending_review' | 'accepted' | 'rejected';

export type LedgerPayload =
	| { kind: 'disown_paper'; work: WorkSubject }
	| { kind: 'claim_paper'; work: WorkSubject }
	| { kind: 'merge_papers'; keep: WorkSubject; drop: WorkSubject }
	| { kind: 'merge_authors'; keep: AuthorSubject; drop: AuthorSubject; note?: string }
	| { kind: 'revoke'; target_event_id: number; reason?: string }
	| {
			kind: 'moderation_decision';
			target_event_id: number;
			decision: 'accepted' | 'rejected';
			reason?: string;
	  }
	| { kind: 'add_paper_request'; work_claim: Record<string, unknown> };

// Client-visible event shape — subset of the full DB row in $lib/server/db.ts
export type LedgerEvent = {
	event_id: number;
	kind: LedgerKind;
	payload: LedgerPayload;
	revoked_at: string | null;
	moderation: ModerationState;
	created_at: string;
};

// Mirror of rankless_rs/src/user_ledger.rs write_final_manifest output
export type AppliedManifest = {
	run_id: string;
	snapshot_at: string;
	applied_event_ids: number[];
	redirected: { event_id: number; subject: string; from: number; to: number }[];
	skipped: { event_id: number; reason: string }[];
};
