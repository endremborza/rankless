// Server plumbing shared by the games: boundary-validation helpers (all game
// endpoints are public) and the size-capped JSON body reader for result POSTs.

import { error } from '@sveltejs/kit';

export const DAY_RE = /^\d{4}-\d{2}-\d{2}$/;
export const SEM_ID_RE = /^[\w.-]{1,80}$/;

const MAX_BODY_BYTES = 2048;

function okNum(v: unknown, lo: number, hi: number): boolean {
	return typeof v === 'number' && Number.isFinite(v) && v >= lo && v <= hi;
}

export function okInt(v: unknown, lo: number, hi: number): boolean {
	return Number.isInteger(v) && okNum(v, lo, hi);
}

export function okSemIdList(v: unknown, maxLen: number): v is string[] {
	return (
		Array.isArray(v) &&
		v.length <= maxLen &&
		v.every((s) => typeof s === 'string' && SEM_ID_RE.test(s))
	);
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
