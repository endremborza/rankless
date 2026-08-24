// Server plumbing shared by the games: lazy per-game schema setup on the user
// DB, boundary-validation helpers (all game endpoints are public), and the
// size-capped JSON body reader for result POSTs.

import { error } from '@sveltejs/kit';

import { getDb } from './db';

export const DAY_RE = /^\d{4}-\d{2}-\d{2}$/;
export const SEM_ID_RE = /^[\w.-]{1,80}$/;

const MAX_BODY_BYTES = 2048;

const ensured = new Set<string>();

export function gameDb(schema: string) {
	const d = getDb();
	if (!ensured.has(schema)) {
		d.run(schema);
		ensured.add(schema);
	}
	return d;
}

function okNum(v: unknown, lo: number, hi: number): boolean {
	return typeof v === 'number' && Number.isFinite(v) && v >= lo && v <= hi;
}

export function okNullNum(v: unknown, lo: number, hi: number): boolean {
	return v === null || okNum(v, lo, hi);
}

export function okInt(v: unknown, lo: number, hi: number): boolean {
	return Number.isInteger(v) && okNum(v, lo, hi);
}

export async function readJsonBody(request: Request): Promise<unknown> {
	const body = await request.text();
	if (body.length > MAX_BODY_BYTES) error(413, 'Result too large');
	try {
		return JSON.parse(body);
	} catch {
		error(400, 'Bad JSON');
	}
}
