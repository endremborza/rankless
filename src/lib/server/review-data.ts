// DB/env glue between the pure review modules and the sqlite cache: the single
// writer of subject_enrichment, and the composer of admin review-queue data.
import { env } from '$env/dynamic/private';
import { EnrichmentDb, LedgerDb, UserDb, VerdictDb, type EventFilter } from './db';
import { fetchPair, neededPairs, type Pair } from './enrich';
import {
	AUTO_MODERATOR,
	composeReviewRows,
	conclusiveClaimIds,
	pairKey,
	pickLatestVerdicts,
	type EnrichmentMap
} from './review';
import { readManifest } from './manifest';
import type { AdminReviewRow } from '$lib/types/review';

const CONCURRENCY = 3;
const PENDING_SCAN_CAP = 10_000;

export type EnrichmentReport = {
	fetched: number;
	remaining: number;
	autoAccepted: number[];
	errors: { source: Pair['source']; key: string; message: string }[];
};

export type ReviewQueuePage = {
	rows: AdminReviewRow[];
	total: number;
	missingEnrichment: number;
	pendingActors: { orcid: string; pending: number }[];
	currentRunId: string | null;
};

// One bounded chunk of external fetches; callers loop until remaining === 0. Existing
// ok/not_found entries are kept (refresh refetches them); error entries always retry.
export async function runEnrichment(limit: number, refresh: boolean): Promise<EnrichmentReport> {
	const pending = listPending();
	const missing = neededPairs(pending).filter((p) => {
		const entry = EnrichmentDb.get(p.source, p.key);
		return !entry || entry.status === 'error' || refresh;
	});

	const batch = missing.slice(0, limit);
	const errors: EnrichmentReport['errors'] = [];
	for (let i = 0; i < batch.length; i += CONCURRENCY) {
		await Promise.all(
			batch.slice(i, i + CONCURRENCY).map(async (pair) => {
				try {
					const result = await fetchPair(pair, env.ENRICH_MAILTO);
					EnrichmentDb.upsert({ ...pair, ...result });
				} catch (e) {
					EnrichmentDb.upsert({ ...pair, status: 'error', data: null });
					errors.push({ ...pair, message: e instanceof Error ? e.message : String(e) });
				}
			})
		);
	}

	const stillPending = listPending();
	const autoAccepted = conclusiveClaimIds(stillPending, loadEnrichmentMap(stillPending)).filter(
		(id) => LedgerDb.setModeration(id, 'accepted', AUTO_MODERATOR)
	);
	return { fetched: batch.length, remaining: missing.length - batch.length, autoAccepted, errors };
}

export function loadReviewQueuePage(
	filter: EventFilter,
	limit: number,
	offset: number
): ReviewQueuePage {
	const events = LedgerDb.listEventsFiltered(filter, limit, offset);
	const total = LedgerDb.countEventsFiltered(filter);
	const enrichment = loadEnrichmentMap(events);
	const verdicts = pickLatestVerdicts(
		VerdictDb.listForOrcids([...new Set(events.map((e) => e.orcid))])
	);
	const users = new Map(UserDb.listUsers().map((u) => [u.orcid, u]));

	const manifest = readManifest();
	const applied = new Set(LedgerDb.getAllAppliedEventIds());
	for (const id of manifest.applied_event_ids) applied.add(id);
	const skipped = new Map(manifest.skipped.map((s) => [s.event_id, s.reason]));

	const pending = listPending();
	const missingEnrichment = neededPairs(pending).filter((p) => {
		const entry = EnrichmentDb.get(p.source, p.key);
		return !entry || entry.status === 'error';
	}).length;

	return {
		rows: composeReviewRows(events, verdicts, users, applied, skipped, enrichment),
		total,
		missingEnrichment,
		pendingActors: LedgerDb.listPendingActors(),
		currentRunId: manifest.run_id || null
	};
}

function listPending() {
	return LedgerDb.listEventsFiltered({ moderation: 'pending_review' }, PENDING_SCAN_CAP, 0).filter(
		(e) => !e.revoked_at
	);
}

function loadEnrichmentMap(events: Parameters<typeof neededPairs>[0]): EnrichmentMap {
	const entries = EnrichmentDb.getMany(neededPairs(events));
	return new Map(entries.map((e) => [pairKey(e.source, e.key), e]));
}
