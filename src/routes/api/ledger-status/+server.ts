import { json } from '@sveltejs/kit';
import { readFileSync } from 'fs';
import { join } from 'path';
import { env } from '$env/dynamic/private';
import { LedgerDb } from '$lib/server/db';

export type AppliedManifest = {
	run_id: string;
	snapshot_at: string;
	applied_event_ids: number[];
	redirected: { event_id: number; subject: string; from: number; to: number }[];
	skipped: { event_id: number; reason: string }[];
};

const EMPTY: AppliedManifest = {
	run_id: '',
	snapshot_at: '',
	applied_event_ids: [],
	redirected: [],
	skipped: []
};

function manifestPath(): string {
	const root = env.OA_ROOT;
	if (!root) throw new Error('OA_ROOT env var not set');
	return join(root, 'user_ledger', 'applied_manifest.json');
}

function readManifest(): AppliedManifest | null {
	try {
		const raw = readFileSync(manifestPath(), 'utf-8');
		return JSON.parse(raw) as AppliedManifest;
	} catch {
		return null;
	}
}

export function GET() {
	const manifest = readManifest();
	if (!manifest || !manifest.run_id) return json(EMPTY);

	LedgerDb.upsertRun(manifest.run_id, manifest.snapshot_at, JSON.stringify(manifest));
	return json(manifest);
}
