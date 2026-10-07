import { APPLIED_MANIFEST, type AppliedManifest } from '$lib/wire/rankless_rs/user_ledger';
import { USER_LEDGER_DIR } from '$lib/paths';
import { readFileSync } from 'fs';
import { join } from 'path';
import { env } from '$env/dynamic/private';

export const EMPTY_MANIFEST: AppliedManifest = {
	run_id: '',
	snapshot_at: '',
	applied_keys: [],
	skipped: []
};

export function manifestPath(): string {
	const root = env.OA_ROOT;
	if (!root) throw new Error('OA_ROOT env var not set');
	return join(root, USER_LEDGER_DIR, APPLIED_MANIFEST);
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
