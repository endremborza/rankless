import type { AppliedManifest, SkipReason } from '$lib/wire/rankless_rs/user_ledger';
import type { LedgerEvent } from '$lib/types/ledger';

// Where an event the served data does not hold stands, as the owner's panel and the admin queue
// both state it.

export const AWAITING_REVIEW = 'awaiting review';

export function skippedStatus(reason: SkipReason): string {
	return `skipped: ${reason}`;
}

export function skipReasons(manifest: AppliedManifest): Map<string, SkipReason> {
	return new Map(manifest.skipped.map((s) => [s.key, s.reason]));
}

// The reason the last run skipped the event, else whether it waits for a moderator; null while it
// only waits for the next run.
export function waitingStatus(
	e: Pick<LedgerEvent, 'key' | 'moderation'>,
	skipped: Map<string, SkipReason>
): string | null {
	const reason = skipped.get(e.key);
	if (reason) return skippedStatus(reason);
	return e.moderation === 'pending_review' ? AWAITING_REVIEW : null;
}
