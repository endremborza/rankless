// Cross-language type boundaries (not covered by type-audit — see docs/type-audit.md):
//
// subject_enrichment.data (TS-written, Python-read): WorkRecord, OrcidRecord
// review_verdicts rows (Python-written, TS-read): ReviewVerdict
//   Mirror: pyscripts/review_ledger.py — WorkRecord, OrcidRecord, Verdict

import type { LedgerKind, ModerationState } from './ledger';

export type EnrichmentSource = 'crossref' | 'openalex' | 'orcid';
export type EnrichmentStatus = 'ok' | 'not_found' | 'error';

export type EnrichedAuthor = {
	name: string;
	orcid: string | null;
	position: number | null;
};

// subject_enrichment.data for source 'crossref' | 'openalex'; key = canonical DOI
export type WorkRecord = {
	title: string | null;
	year: number | null;
	venue: string | null;
	oa_work_id: string | null; // 'W…', openalex only
	authors: EnrichedAuthor[];
};

// subject_enrichment.data for source 'orcid'; key = bare ORCID
export type OrcidRecord = {
	name: string | null;
	work_dois: string[];
	work_titles: string[];
	n_works: number;
};

export type EnrichmentEntry = {
	source: EnrichmentSource;
	key: string;
	status: EnrichmentStatus;
	data: WorkRecord | OrcidRecord | null;
	fetched_at: string;
};

export type ReviewVerdictValue = 'approve' | 'reject' | 'unsure';

export type ReviewVerdict = {
	orcid: string;
	kind: string;
	subject_hash: string;
	model: string;
	verdict: ReviewVerdictValue;
	confidence: number;
	reasoning: string;
	checks: Record<string, unknown> | null;
	created_at: string;
};

export type HardEvidence = {
	conclusive: boolean;
	sources: EnrichmentSource[];
};

// --- Admin review queue rows (server-composed, markup-ready) --- //

export type ReviewWorkCell = {
	title: string | null;
	year: number | null;
	venue: string | null;
	doi: string | null; // canonical
	oa_work_id: string | null;
	enriched: boolean;
};

export type PipelineCell = { label: string; cls: 'applied' | 'skipped' | 'awaiting' | 'muted' };

export type AdminReviewRow = {
	event_id: number;
	orcid: string;
	kind: LedgerKind;
	created_at: string;
	revoked_at: string | null;
	moderation: ModerationState;
	moderated_by: string | null;
	moderated_at: string | null;
	auto_moderated: boolean;
	summary: string;
	actor_name: string | null;
	actor_semantic_id: string | null;
	work: ReviewWorkCell | null; // claim/disown only; other kinds rely on summary
	verdict: ReviewVerdict | null;
	hard: HardEvidence | null;
	pipeline: PipelineCell;
};
