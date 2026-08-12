import { createHash } from 'crypto';
import type {
	LedgerKind,
	LedgerPayload,
	ModerationState,
	WorkSubject,
	AuthorSubject
} from '$lib/types/ledger';

export const DEFAULT_MODERATION: Record<LedgerKind, ModerationState> = {
	disown_paper: 'auto_ok',
	claim_paper: 'pending_review',
	merge_papers: 'auto_ok',
	merge_authors: 'pending_review',
	revoke: 'auto_ok',
	moderation_decision: 'auto_ok',
	add_paper_request: 'pending_review'
};

// Merge-stable logical id of an event: `${orcid}|${kind}|${subject_hash}`. This is the
// dedup identity the DB already enforces (idx_le_dedup), and — unlike the autoincrement
// event_id — it survives DB merges. Mirrored verbatim in export_user_ledger.py and the
// one-time revoke migration; keep the format in sync.
export function logicalKey(orcid: string, kind: LedgerKind, subjectHash: string): string {
	return `${orcid}|${kind}|${subjectHash}`;
}

export function workCanonicalKey(ws: WorkSubject): string {
	if (ws.oa_id !== null && ws.oa_id !== undefined) return `oa:${ws.oa_id}`;
	if (ws.doi) return `doi:${ws.doi.toLowerCase()}`;
	throw new Error('work subject has no stable identifier');
}

export function authorCanonicalKey(as: AuthorSubject): string {
	if (as.orcid) return `orcid:${as.orcid}`;
	if (as.oa_id !== null && as.oa_id !== undefined) return `oa:${as.oa_id}`;
	throw new Error('author subject has no stable identifier');
}

function sha1Hex(s: string): string {
	return createHash('sha1').update(s).digest('hex');
}

export function subjectHash(payload: LedgerPayload): string {
	switch (payload.kind) {
		case 'disown_paper':
		case 'claim_paper':
			return sha1Hex(workCanonicalKey(payload.work));
		case 'merge_papers': {
			const keys = [workCanonicalKey(payload.keep), workCanonicalKey(payload.drop)].sort();
			return sha1Hex(keys.join('|'));
		}
		case 'merge_authors': {
			const keys = [authorCanonicalKey(payload.keep), authorCanonicalKey(payload.drop)].sort();
			return sha1Hex(keys.join('|'));
		}
		case 'revoke':
			// Keyed on the target's merge-stable logical key, not a renumberable event_id.
			return sha1Hex(`target:${payload.target_key}`);
		case 'moderation_decision':
			return sha1Hex(`target:${payload.target_event_id}`);
		case 'add_paper_request':
			return sha1Hex(JSON.stringify(payload.work_claim));
	}
}
