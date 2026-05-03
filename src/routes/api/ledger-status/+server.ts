import { json } from '@sveltejs/kit';
import { LedgerDb } from '$lib/server/db';
import { readManifest, EMPTY_MANIFEST } from '$lib/server/manifest';
export type { AppliedManifest } from '$lib/types/ledger';

export function GET() {
	const manifest = readManifest();
	if (!manifest.run_id) return json(EMPTY_MANIFEST);
	LedgerDb.upsertRun(manifest.run_id, manifest.snapshot_at, JSON.stringify(manifest));
	return json(manifest);
}
