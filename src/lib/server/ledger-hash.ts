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
		case 'moderation_decision':
			return sha1Hex(`target:${payload.target_event_id}`);
		case 'add_paper_request':
			return sha1Hex(JSON.stringify(payload.work_claim));
	}
}
