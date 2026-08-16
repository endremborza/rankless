// Shape of the baked release report (src/lib/assets/data/release-report.json),
// produced by pyscripts/release_report.py from the $OA_ROOT/releases records.
// Snake_case keys cross the Python→site boundary verbatim.

export type ReportStep = { label: string; kept: number };

export type EntityChain = { steps: ReportStep[]; final: number };

export type LedgerAggregates = {
	sources: number;
	events: number;
	applied: Record<string, number>;
	applied_total: number;
	skipped: Record<string, number>;
	skipped_total: number;
};

// Aggregates of the forced-works sidecar (counts only; the wid list stays private).
export type RestoredAggregates = {
	cohort: number;
	forced_total: number;
	outside_standard: number;
	outside_type: number;
	outside_citations: number;
	claim_auto: number;
	claim_merged: number;
	author_rescues: number;
};

// Aggregates of the claims-review sidecar; unresolved_by_cause is cause → count.
export type ClaimsAggregates = {
	submitted: number;
	applied: number;
	unresolved: number;
	unresolved_by_cause: Record<string, number>;
	merges_reviewed: number;
	merges_approved: number;
};

export type DeltaTriple = { previous: number; current: number; change: number };

export type AppliedDelta = { previous: number; current: number; new: number };

export type ReleaseDeltas = {
	entities: Record<string, DeltaTriple>;
	applied: Record<string, AppliedDelta>;
	applied_total: AppliedDelta;
};

export type ReleaseSnapshot = { name: string; date: string | null };

export type ReleaseReport = {
	run_id: string;
	stamp: string;
	git_commit: string;
	snapshot: ReleaseSnapshot;
	entities: Record<string, EntityChain>;
	ledger: LedgerAggregates;
	restored: RestoredAggregates | null;
	claims: ClaimsAggregates | null;
	previous: { run_id: string; snapshot: ReleaseSnapshot } | null;
	deltas: ReleaseDeltas | null;
};
