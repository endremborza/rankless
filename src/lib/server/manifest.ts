import { readFileSync } from 'fs';
import { join } from 'path';
import { env } from '$env/dynamic/private';
import type { AppliedManifest } from '$lib/types/ledger';

export const EMPTY_MANIFEST: AppliedManifest = {
	run_id: '',
	snapshot_at: '',
	applied_event_ids: [],
	redirected: [],
	skipped: []
};

export function manifestPath(): string {
	const root = env.OA_ROOT;
	if (!root) throw new Error('OA_ROOT env var not set');
	return join(root, 'user-ledger', 'applied_manifest.json');
}

export function readManifest(): AppliedManifest {
	try {
		const raw = readFileSync(manifestPath(), 'utf-8');
		const m = JSON.parse(raw) as AppliedManifest;
		return m.run_id ? m : EMPTY_MANIFEST;
	} catch {
		return EMPTY_MANIFEST;
	}
}
