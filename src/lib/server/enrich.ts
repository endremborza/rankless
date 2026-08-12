// Pure fetch + pluck layer for external metadata (Crossref, OpenAlex, ORCID).
// No DB or env access (keeps this vitest-importable); orchestration and the
// enrichment cache live in review-data.ts — the single writer of that cache.
import { canonicalDoi, claimedWork, normalizeOrcid } from './review';
import type { LedgerEvent } from './db';
import type {
	EnrichedAuthor,
	EnrichmentEntry,
	EnrichmentSource,
	OrcidRecord,
	WorkRecord
} from '$lib/types/review';

const FETCH_TIMEOUT_MS = 10_000;
const ORCID_WORKS_CAP = 500;
const ORCID_TITLES_CAP = 50;

export type Pair = { source: EnrichmentSource; key: string };
export type FetchResult = {
	status: EnrichmentEntry['status'];
	data: WorkRecord | OrcidRecord | null;
};

// --- pure pluckers (exported for tests) --- //

export function pluckCrossref(json: unknown): WorkRecord {
	const m = (json as { message?: Record<string, unknown> }).message ?? {};
	const issued = (m['issued'] as { 'date-parts'?: number[][] })?.['date-parts']?.[0]?.[0];
	const authors = ((m['author'] as Record<string, unknown>[]) ?? []).map(
		(a, i): EnrichedAuthor => ({
			name: [a['given'], a['family']].filter(Boolean).join(' '),
			orcid: typeof a['ORCID'] === 'string' ? normalizeOrcid(a['ORCID']) : null,
			position: i
		})
	);
	return {
		title: firstString(m['title']),
		year: typeof issued === 'number' ? issued : null,
		venue: firstString(m['container-title']),
		oa_work_id: null,
		authors
	};
}

export function pluckOpenAlex(json: unknown): WorkRecord {
	const w = json as Record<string, unknown>;
	const authorships = (w['authorships'] as Record<string, unknown>[]) ?? [];
	const authors = authorships.map((a, i): EnrichedAuthor => {
		const author = (a['author'] as Record<string, unknown>) ?? {};
		return {
			name: typeof author['display_name'] === 'string' ? author['display_name'] : '',
			orcid: typeof author['orcid'] === 'string' ? normalizeOrcid(author['orcid']) : null,
			position: i
		};
	});
	const source = (
		(w['primary_location'] as Record<string, unknown>)?.['source'] as Record<string, unknown>
	)?.['display_name'];
	const id = w['id'];
	return {
		title: typeof w['title'] === 'string' ? w['title'] : null,
		year: typeof w['publication_year'] === 'number' ? w['publication_year'] : null,
		venue: typeof source === 'string' ? source : null,
		oa_work_id: typeof id === 'string' ? (id.split('/').pop() ?? null) : null,
		authors
	};
}

export function pluckOrcid(recordJson: unknown, worksJson: unknown): OrcidRecord {
	const person = (recordJson as { person?: Record<string, unknown> }).person ?? {};
	const nameObj = (person['name'] as Record<string, unknown>) ?? {};
	const credit = (nameObj['credit-name'] as { value?: string })?.value;
	const given = (nameObj['given-names'] as { value?: string })?.value;
	const family = (nameObj['family-name'] as { value?: string })?.value;
	const name = credit ?? ([given, family].filter(Boolean).join(' ') || null);

	const groups = ((worksJson as { group?: Record<string, unknown>[] }).group ?? []).slice(
		0,
		ORCID_WORKS_CAP
	);
	const dois = new Set<string>();
	const titles: string[] = [];
	for (const g of groups) {
		const ids =
			((g['external-ids'] as Record<string, unknown>)?.['external-id'] as Record<
				string,
				unknown
			>[]) ?? [];
		for (const id of ids) {
			if (id['external-id-type'] === 'doi' && typeof id['external-id-value'] === 'string') {
				dois.add(canonicalDoi(id['external-id-value']));
			}
		}
		const summary = (g['work-summary'] as Record<string, unknown>[])?.[0];
		const title = ((summary?.['title'] as Record<string, unknown>)?.['title'] as { value?: string })
			?.value;
		if (title && titles.length < ORCID_TITLES_CAP) titles.push(title);
	}
	return { name, work_dois: [...dois], work_titles: titles, n_works: groups.length };
}

// --- fetchers --- //

export async function fetchPair(pair: Pair, mailto: string | undefined): Promise<FetchResult> {
	const headers: Record<string, string> = mailto
		? { 'User-Agent': `rankless (mailto:${mailto})` }
		: {};
	switch (pair.source) {
		case 'crossref': {
			const json = await getJson(
				`https://api.crossref.org/works/${encodeURIComponent(pair.key)}`,
				headers
			);
			return json === 'not_found'
				? { status: 'not_found', data: null }
				: { status: 'ok', data: pluckCrossref(json) };
		}
		case 'openalex': {
			const suffix = mailto ? `?mailto=${encodeURIComponent(mailto)}` : '';
			const json = await getJson(
				`https://api.openalex.org/works/doi:${encodeURIComponent(pair.key)}${suffix}`,
				headers
			);
			return json === 'not_found'
				? { status: 'not_found', data: null }
				: { status: 'ok', data: pluckOpenAlex(json) };
		}
		case 'orcid': {
			const accept = { ...headers, Accept: 'application/json' };
			const record = await getJson(`https://pub.orcid.org/v3.0/${pair.key}/record`, accept);
			if (record === 'not_found') return { status: 'not_found', data: null };
			const works = await getJson(`https://pub.orcid.org/v3.0/${pair.key}/works`, accept);
			return { status: 'ok', data: pluckOrcid(record, works === 'not_found' ? {} : works) };
		}
	}
}

// Every (source, key) a set of events needs for display + hard-evidence + AI review:
// both work sources per claimed DOI, one ORCID record per distinct actor.
export function neededPairs(events: LedgerEvent[]): Pair[] {
	const pairs = new Map<string, Pair>();
	const add = (source: EnrichmentSource, key: string) =>
		pairs.set(`${source}|${key}`, { source, key });
	for (const e of events) {
		add('orcid', normalizeOrcid(e.orcid));
		if (e.kind !== 'claim_paper') continue;
		const doi = claimedWork(e.payload)?.doi;
		if (doi) {
			const key = canonicalDoi(doi);
			add('crossref', key);
			add('openalex', key);
		}
	}
	return [...pairs.values()];
}

async function getJson(
	url: string,
	headers: Record<string, string>
): Promise<unknown | 'not_found'> {
	const res = await fetch(url, { headers, signal: AbortSignal.timeout(FETCH_TIMEOUT_MS) });
	if (res.status === 404) return 'not_found';
	if (!res.ok) throw new Error(`${res.status} for ${url}`);
	return res.json();
}

function firstString(v: unknown): string | null {
	return Array.isArray(v) && typeof v[0] === 'string' ? v[0] : null;
}
