// Pure review-domain logic: no DB or env access, so it stays unit-testable under
// vitest (bun:sqlite cannot be imported there). DB glue lives in review-data.ts.
import { fixName } from '$lib/name-overrides';
import type { LedgerEvent, UserRow } from './db';
import type { LedgerPayload, WorkSubject } from '$lib/types/ledger';
import type {
	AdminReviewRow,
	EnrichmentEntry,
	EnrichmentSource,
	HardEvidence,
	OrcidRecord,
	PipelineCell,
	ReviewVerdict,
	ReviewWorkCell,
	WorkRecord
} from '$lib/types/review';

export const AUTO_MODERATOR = 'auto:doi-authorship';

// Enrichment entries keyed by pairKey(source, key).
export type EnrichmentMap = Map<string, EnrichmentEntry>;

export function pairKey(source: EnrichmentSource, key: string): string {
	return `${source}|${key}`;
}

export function normalizeOrcid(s: string): string {
	return s
		.trim()
		.replace(/^https?:\/\/(www\.)?orcid\.org\//i, '')
		.toUpperCase();
}

export function canonicalDoi(doi: string): string {
	return doi
		.trim()
		.replace(/^https?:\/\/(dx\.)?doi\.org\//i, '')
		.toLowerCase();
}

// Publisher/OpenAlex-asserted authorship: the claimant's ORCID appearing in either
// source's author list proves the claim without human judgment.
export function evaluateDoiAuthorship(
	claimantOrcid: string,
	crossref: WorkRecord | null,
	openalex: WorkRecord | null
): HardEvidence {
	const target = normalizeOrcid(claimantOrcid);
	const listsTarget = (rec: WorkRecord | null): boolean =>
		!!rec && rec.authors.some((a) => a.orcid !== null && normalizeOrcid(a.orcid) === target);
	const sources: EnrichmentSource[] = [];
	if (listsTarget(crossref)) sources.push('crossref');
	if (listsTarget(openalex)) sources.push('openalex');
	return { conclusive: sources.length > 0, sources };
}

export function verdictKey(orcid: string, kind: string, subjectHash: string): string {
	return `${orcid}|${kind}|${subjectHash}`;
}

// Latest verdict per subject wins for display, regardless of which model produced it.
export function pickLatestVerdicts(verdicts: ReviewVerdict[]): Map<string, ReviewVerdict> {
	const latest = new Map<string, ReviewVerdict>();
	for (const v of verdicts) {
		const key = verdictKey(v.orcid, v.kind, v.subject_hash);
		const cur = latest.get(key);
		if (!cur || v.created_at > cur.created_at) latest.set(key, v);
	}
	return latest;
}

export function isAutoModerated(moderatedBy: string | null): boolean {
	return moderatedBy !== null && moderatedBy.startsWith('auto:');
}

export function claimedWork(payload: LedgerPayload): WorkSubject | null {
	return payload.kind === 'claim_paper' || payload.kind === 'disown_paper' ? payload.work : null;
}

// Pending claims proven by the enrichment at hand; caller flips their moderation.
export function conclusiveClaimIds(events: LedgerEvent[], enrichment: EnrichmentMap): number[] {
	const ids: number[] = [];
	for (const e of events) {
		if (e.kind !== 'claim_paper' || e.moderation !== 'pending_review' || e.revoked_at) continue;
		const doi = claimedWork(e.payload)?.doi;
		if (!doi) continue;
		const key = canonicalDoi(doi);
		const crossref = workRecord(enrichment.get(pairKey('crossref', key)));
		const openalex = workRecord(enrichment.get(pairKey('openalex', key)));
		if (evaluateDoiAuthorship(e.orcid, crossref, openalex).conclusive) ids.push(e.event_id);
	}
	return ids;
}

export function composeReviewRows(
	events: LedgerEvent[],
	verdicts: Map<string, ReviewVerdict>,
	users: Map<string, UserRow>,
	applied: Set<string>,
	skipped: Map<string, string>,
	enrichment: EnrichmentMap
): AdminReviewRow[] {
	return events.map((e) => {
		const { work, hard } = workEvidence(e, enrichment);
		return {
			event_id: e.event_id,
			orcid: e.orcid,
			kind: e.kind,
			created_at: e.created_at,
			revoked_at: e.revoked_at,
			moderation: e.moderation,
			moderated_by: e.moderated_by,
			moderated_at: e.moderated_at,
			auto_moderated: isAutoModerated(e.moderated_by),
			summary: summarize(e.payload),
			actor_name: actorName(e.orcid, users, enrichment),
			actor_semantic_id: users.get(e.orcid)?.semantic_id ?? null,
			work,
			verdict: verdicts.get(verdictKey(e.orcid, e.kind, e.subject_hash)) ?? null,
			hard,
			pipeline: pipelineCell(e, applied, skipped)
		};
	});
}

// All snapshot/enrichment values are untrusted external data — render them via plain
// `{}` interpolation only (Svelte auto-escapes). Do NOT switch consumers to {@html}.
export function summarize(p: LedgerPayload): string {
	switch (p.kind) {
		case 'disown_paper':
			return `disown “${p.work.display_snapshot.title || p.work.doi || p.work.oa_id || '?'}”`;
		case 'claim_paper':
			return `claim “${p.work.display_snapshot.title || p.work.doi || p.work.oa_id || '?'}”`;
		case 'merge_papers':
			return `keep “${p.keep.display_snapshot.title}” ⇐ drop “${p.drop.display_snapshot.title}”`;
		case 'merge_authors':
			return `keep “${p.keep.display_snapshot.display_name}” ⇐ drop “${p.drop.display_snapshot.display_name}”${p.note ? ` — note: ${p.note}` : ''}`;
		case 'revoke':
			return `revoke ${p.target_key}${p.reason ? ` — ${p.reason}` : ''}`;
		case 'moderation_decision':
			return `${p.decision} event #${p.target_event_id}`;
		case 'add_paper_request':
			return 'add-paper request';
	}
}

function actorName(
	orcid: string,
	users: Map<string, UserRow>,
	enrichment: EnrichmentMap
): string | null {
	const entry = enrichment.get(pairKey('orcid', normalizeOrcid(orcid)));
	const record = entry?.status === 'ok' ? (entry.data as OrcidRecord | null) : null;
	const name = users.get(orcid)?.name ?? record?.name ?? null;
	return name ? fixName(name) : null;
}

function workRecord(entry: EnrichmentEntry | undefined): WorkRecord | null {
	if (!entry || entry.status !== 'ok' || !entry.data) return null;
	return entry.data as WorkRecord;
}

function workEvidence(
	e: LedgerEvent,
	enrichment: EnrichmentMap
): { work: ReviewWorkCell | null; hard: HardEvidence | null } {
	const subject = claimedWork(e.payload);
	if (!subject) return { work: null, hard: null };
	const doi = subject.doi ? canonicalDoi(subject.doi) : null;
	const crossref = doi ? workRecord(enrichment.get(pairKey('crossref', doi))) : null;
	const openalex = doi ? workRecord(enrichment.get(pairKey('openalex', doi))) : null;
	const enriched = crossref !== null || openalex !== null;
	const work: ReviewWorkCell = {
		title: crossref?.title ?? openalex?.title ?? (subject.display_snapshot.title || null),
		year: crossref?.year ?? openalex?.year ?? subject.display_snapshot.year,
		venue: crossref?.venue ?? openalex?.venue ?? null,
		doi,
		oa_work_id: openalex?.oa_work_id ?? null,
		enriched
	};
	const hard =
		e.kind === 'claim_paper' && enriched
			? evaluateDoiAuthorship(e.orcid, crossref, openalex)
			: null;
	return { work, hard };
}

// Whether (and how) a requested change has reached the live data. `applied` unions
// every pipeline run's applied ids, so this answers "is this change implemented yet?".
function pipelineCell(
	e: LedgerEvent,
	applied: Set<string>,
	skipped: Map<string, string>
): PipelineCell {
	// Keyed by the merge-stable logical key, not event_id (renumbers on DB merge). Revokes
	// are control actions collapsed out of the manifest, so classify them before the
	// applied/skipped lookup rather than letting them fall to "awaiting rebuild".
	if (e.revoked_at || e.moderation === 'rejected') return { label: '—', cls: 'muted' };
	if (e.kind === 'revoke') return { label: 'revocation', cls: 'muted' };
	if (applied.has(e.key)) return { label: 'implemented', cls: 'applied' };
	const reason = skipped.get(e.key);
	if (reason) return { label: `skipped · ${reason}`, cls: 'skipped' };
	if (e.moderation === 'pending_review') return { label: 'awaiting review', cls: 'muted' };
	return { label: 'awaiting rebuild', cls: 'awaiting' };
}
