import { BE_URL } from '$lib/constants';
import type { WorkSubject, AuthorSubject } from '$lib/types/ledger';

type WorkResolveResp = {
	oaId: number;
	wid: number;
	doi: string;
	year: number;
	name: string;
};

type AuthorResolveResp = {
	oaId: number;
	dmId: number;
	semanticId: string;
	orcid?: string;
	name: string;
};

export class ResolveError extends Error {
	constructor(
		message: string,
		public readonly status: number = 422
	) {
		super(message);
	}
}

// run_id is filled in once Phase 3 lands `ledger_runs` and the server can
// surface the latest applied run. Until then, leave null so the manifest
// step can stamp it later if needed.
const RUN_ID: string | null = null;

async function fetchResolve<T>(
	path: string,
	params: Record<string, string | number | undefined>
): Promise<T | null> {
	const usp = new URLSearchParams();
	for (const [k, v] of Object.entries(params)) {
		if (v !== undefined && v !== '') usp.set(k, String(v));
	}
	const qs = usp.toString();
	if (!qs) return null;
	const resp = await fetch(`${BE_URL}${path}?${qs}`);
	if (resp.status === 200) return (await resp.json()) as T;
	if (resp.status === 404) return null;
	throw new ResolveError(`${path} backend returned ${resp.status}`, 502);
}

export async function resolveWorkSubject(input: {
	wid?: number;
	oa_id?: number;
	doi?: string;
	display_title?: string;
	display_year?: number;
}): Promise<WorkSubject> {
	let live: WorkResolveResp | null = null;
	if (input.wid !== undefined || input.oa_id !== undefined) {
		live = await fetchResolve<WorkResolveResp>('/resolve/work', {
			wid: input.wid,
			oa_id: input.oa_id
		});
	}
	const oa_id = live?.oaId ?? input.oa_id ?? null;
	const doi = (live?.doi || input.doi || '').toLowerCase().trim() || null;
	if (oa_id === null && doi === null) {
		throw new ResolveError(
			'work subject needs at least one of: wid, oa_id, doi (UI may be stale — refresh and retry)'
		);
	}
	return {
		oa_id,
		doi,
		dm_id_at_creation: live?.wid ?? input.wid ?? null,
		semantic_id_at_creation: null,
		run_id_at_creation: RUN_ID,
		display_snapshot: {
			title: live?.name ?? input.display_title ?? '',
			year: live?.year ?? input.display_year ?? null
		}
	};
}

export async function resolveAuthorSubject(input: {
	semantic_id?: string;
	orcid?: string;
	oa_id?: number;
	dm_id?: number;
	display_name?: string;
}): Promise<AuthorSubject> {
	const live = await fetchResolve<AuthorResolveResp>('/resolve/author', {
		semantic_id: input.semantic_id,
		orcid: input.orcid,
		oa_id: input.oa_id,
		dm_id: input.dm_id
	});
	const oa_id = live?.oaId ?? input.oa_id ?? null;
	const orcid = live?.orcid ?? input.orcid ?? null;
	if (oa_id === null && orcid === null) {
		throw new ResolveError(
			'author subject needs at least one of: oa_id, orcid (UI may be stale — refresh and retry)'
		);
	}
	return {
		oa_id,
		orcid,
		dm_id_at_creation: live?.dmId ?? input.dm_id ?? null,
		semantic_id_at_creation: live?.semanticId ?? input.semantic_id ?? null,
		run_id_at_creation: RUN_ID,
		display_snapshot: {
			display_name: live?.name ?? input.display_name ?? ''
		}
	};
}

export type OrcidProfile = { name: string; semanticId: string };

export async function resolveOrcidProfiles(
	orcids: Iterable<string>
): Promise<Map<string, OrcidProfile>> {
	const out = new Map<string, OrcidProfile>();
	await Promise.all(
		[...orcids].map(async (orcid) => {
			try {
				const resp = await fetch(`${BE_URL}/orcid/${encodeURIComponent(orcid)}`);
				if (resp.status !== 200) return;
				const r = (await resp.json()) as { name?: string; semanticId?: string } | null;
				out.set(orcid, { name: r?.name ?? '', semanticId: r?.semanticId ?? '' });
			} catch {
				// backend unreachable — omit so the caller retries later.
			}
		})
	);
	return out;
}

export function canonicalDoi(doi: string): string {
	return doi
		.trim()
		.toLowerCase()
		.replace(/^https?:\/\/(dx\.)?doi\.org\//, '');
}

// Authorization gate for merge_papers: the actor may only merge papers they authored.
// Throws ResolveError(403) unless `orcid` authored at least one of the given work ids
// (checked against the backend's per-author production set). A work id that can't be
// resolved to a dm_id is unverifiable, so an all-null input fails closed.
export async function assertAuthoredAny(orcid: string, wids: (number | null)[]): Promise<void> {
	const toCheck = wids.filter((w): w is number => typeof w === 'number');
	if (toCheck.length === 0) {
		throw new ResolveError('cannot verify paper authorship (UI may be stale — refresh and retry)');
	}
	const verdicts = await Promise.all(
		toCheck.map((wid) =>
			fetch(`${BE_URL}/authored?orcid=${encodeURIComponent(orcid)}&wid=${wid}`)
				.then((r) => (r.ok ? r.json() : null))
				.then((j: { authored?: boolean } | null) => j?.authored === true)
				.catch(() => false)
		)
	);
	if (!verdicts.some(Boolean)) {
		throw new ResolveError('you can only merge papers you authored', 403);
	}
}
