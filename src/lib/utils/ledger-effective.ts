import type { LedgerEvent, AppliedManifest } from '$lib/types/ledger';

export function computeEffective(
	events: LedgerEvent[],
	manifest: AppliedManifest
): { disownedWids: Set<number>; mergedPairs: [number, number][] } {
	const appliedKeys = new Set(manifest.applied_keys);

	const pendingRevokeTargets = new Set<string>();
	for (const e of events) {
		if (e.kind === 'revoke' && e.revoked_at === null && e.payload.kind === 'revoke') {
			if (appliedKeys.has(e.payload.target_key)) {
				pendingRevokeTargets.add(e.payload.target_key);
			}
		}
	}

	const disownedWids = new Set<number>();
	const mergedPairs: [number, number][] = [];

	for (const e of events) {
		if (e.revoked_at !== null) continue;
		if (pendingRevokeTargets.has(e.key)) continue;
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
