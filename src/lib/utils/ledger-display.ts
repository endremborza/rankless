import type {
	AppliedManifest,
	AuthorSubject,
	SkipReason,
	WorkSubject
} from '$lib/wire/rankless_rs/user_ledger';
import type { PaperOut } from '$lib/wire/rankless_server/responses';
import type { LedgerEvent } from '$lib/types/ledger';
import { runDate } from '$lib/text-format-util';
import { canonicalDoi } from '$lib/utils/identifiers';
import { draftOf, type ComposeKind } from '$lib/utils/ledger-client';
import { undoEvents } from '$lib/utils/ledger-effective';
import { skipReasons, waitingStatus } from '$lib/utils/ledger-status';
import { htmlToText } from '$lib/utils/paper-helpers';

// The owner's served works, each under its OpenAlex id (number) and its canonical DOI (string).
export type PaperMap = Map<number | string, PaperOut>;

// What a subject or an event reads as, and what the reader should know about that text.
export type SubjectText = { text: string; note: string | null };

export type RowAction = 'undo' | 'cancel_undo' | 'change' | 'edit' | 'withdraw';

export type PanelRow = SubjectText & {
	event: LedgerEvent;
	status: string | null;
	actions: RowAction[];
	// the pending revoke of an applied event: what `cancel_undo` withdraws
	undoEventId: number | null;
};

type DisplayContext = { events: LedgerEvent[]; papers: PaperMap; runId: string };

type FormCopy = { submitLabel: string; doneText: string };

export const NOT_IN_DATA = 'not in the current data';
export const UNDO_PENDING = 'undo pending';

export const ACTION_LABELS: Record<RowAction, string> = {
	undo: 'Undo',
	cancel_undo: 'Cancel undo',
	change: 'Change',
	edit: 'Edit',
	withdraw: '×'
};

// Each composed kind's section of the panel and the text of its form.
export const COMPOSE_COPY: Record<
	ComposeKind,
	FormCopy & { title: string; hint: string | null; identifier: string; note: string | null }
> = {
	claim_paper: {
		title: 'Claim a Paper',
		hint: null,
		identifier: 'Enter DOI',
		note: null,
		submitLabel: 'Claim',
		doneText: 'Claimed'
	},
	merge_authors: {
		title: 'Report Duplicate Profile',
		hint: 'If another author profile represents the same person, submit a merge request. A human will review it before any changes are applied.',
		identifier: 'Profile URL or semantic ID',
		note: 'Optional note (e.g. institution, ORCID, DOI of shared paper)',
		submitLabel: 'Submit Request',
		doneText: 'Submitted for review'
	}
};

// The form a row's Change or Edit opens.
export const REPLACE_COPY: FormCopy = { submitLabel: 'Save', doneText: 'Saved' };

// The panel's two lists: what the served data reflects, and what waits for the next run.
export const PANEL_SECTIONS = {
	applied: 'Applied',
	pending: 'Pending — next data refresh'
} as const;

// The owner's actions on the works list's rows and its merge bar.
export const WORKS_ACTIONS = {
	remove: 'Remove',
	selectForMerge: 'Select for merge',
	mergeInto: (drops: number) => `Merge ${drops} into the kept paper`
};

// What an event's text starts with, by kind.
export const EVENT_LABELS = {
	disown_paper: 'Removed: ',
	claim_paper: 'Claimed: ',
	merge_papers: 'Merged ',
	merge_authors: 'Author merge: drop ',
	revoke: 'Undo: '
} as const;

// The skips that mean the run found no record under the event's identifier: a corrected
// identifier is the fix.
export const ORPHAN_REASONS: ReadonlySet<SkipReason> = new Set([
	'missing_oa_id',
	'missing_oa_id_or_orcid',
	'oa_id_not_in_dataset',
	'doi_not_in_snapshot'
]);

export function paperMapOf(papers: PaperOut[]): PaperMap {
	const map: PaperMap = new Map();
	for (const p of papers) {
		map.set(p.oaId, p);
		if (p.doi) map.set(canonicalDoi(p.doi), p);
	}
	return map;
}

// A work as the served data names it, else as the event recorded it, else by its identifier.
export function workText(work: WorkSubject, papers: PaperMap, runId: string): SubjectText {
	const live =
		(work.oa_id != null ? papers.get(work.oa_id) : undefined) ??
		(work.doi ? papers.get(work.doi) : undefined);
	if (live) return { text: quoted(live.name), note: null };
	const title = work.display_snapshot?.title;
	if (title) return { text: quoted(title), note: snapshotNote(work.run_id_at_creation, runId) };
	const id = work.doi ?? (work.oa_id != null ? `W${work.oa_id}` : 'Untitled');
	return { text: id, note: NOT_IN_DATA };
}

// An author record as the event recorded it, else by its identifier; the page holds no author
// records to look one up in.
export function authorText(author: AuthorSubject, runId: string): SubjectText {
	const name = author.display_snapshot?.display_name;
	if (name) return { text: name, note: snapshotNote(author.run_id_at_creation, runId) };
	const id = author.orcid ?? (author.oa_id != null ? `A${author.oa_id}` : 'Unnamed');
	return { text: id, note: NOT_IN_DATA };
}

export function describeEvent(e: LedgerEvent, ctx: DisplayContext): SubjectText {
	const p = e.payload;
	const work = (w: WorkSubject) => workText(w, ctx.papers, ctx.runId);
	switch (p.kind) {
		case 'disown_paper':
		case 'claim_paper':
			return labelled(EVENT_LABELS[p.kind], work(p.work));
		case 'merge_papers': {
			const [keep, drop] = [work(p.keep), work(p.drop)];
			return {
				text: `${EVENT_LABELS.merge_papers}${keep.text} ← ${drop.text}`,
				note: [...new Set([keep.note, drop.note])].filter(Boolean).join('; ') || null
			};
		}
		case 'merge_authors':
			return labelled(EVENT_LABELS.merge_authors, authorText(p.drop, ctx.runId));
		case 'revoke': {
			const target = ctx.events.find((t) => t.key === p.target_key);
			return target
				? labelled(EVENT_LABELS.revoke, describeEvent(target, ctx))
				: { text: 'Undo of a previous change', note: null };
		}
		default:
			return { text: e.kind, note: null };
	}
}

// The owner's events as the panel lists them: what the served data already reflects, and what
// waits for the next run, each with its status and the actions it offers.
export function panelRows(
	events: LedgerEvent[],
	manifest: AppliedManifest,
	papers: PaperMap
): { applied: PanelRow[]; pending: PanelRow[] } {
	const ctx = { events, papers, runId: manifest.run_id };
	const appliedKeys = new Set(manifest.applied_keys);
	const skipped = skipReasons(manifest);
	const undone = undoEvents(events);

	const applied: PanelRow[] = [];
	const pending: PanelRow[] = [];
	for (const event of events) {
		if (event.revoked_at !== null || event.kind === 'moderation_decision') continue;
		const row = { event, ...describeEvent(event, ctx) };
		const undoEventId = undone.get(event.key) ?? null;
		if (event.payload.kind === 'revoke') {
			// an undo waits for the next run only while this one still serves its target
			if (appliedKeys.has(event.payload.target_key))
				pending.push({ ...row, status: null, actions: [], undoEventId: null });
		} else if (appliedKeys.has(event.key)) {
			applied.push({
				...row,
				status: undoEventId === null ? null : UNDO_PENDING,
				actions:
					undoEventId !== null ? ['cancel_undo'] : composed(event) ? ['undo', 'change'] : ['undo'],
				undoEventId
			});
		} else if (undoEventId === null) {
			const reason = skipped.get(event.key);
			const orphan = reason !== undefined && ORPHAN_REASONS.has(reason);
			pending.push({
				...row,
				status: waitingStatus(event, skipped),
				actions: orphan && composed(event) ? ['edit', 'withdraw'] : ['withdraw'],
				undoEventId
			});
		}
	}
	return { applied, pending };
}

// A kind the panel composes in a form can be rewritten in one.
function composed(event: LedgerEvent): boolean {
	return draftOf(event.payload) !== null;
}

function quoted(title: string): string {
	return `"${htmlToText(title)}"`;
}

function labelled(label: string, subject: SubjectText): SubjectText {
	return { text: label + subject.text, note: subject.note };
}

// A snapshot taken under the served run reads as current; one from another run says so.
function snapshotNote(runAtCreation: string | null, runId: string): string | null {
	return runAtCreation && runAtCreation !== runId
		? `as of the release of ${runDate(runAtCreation)}`
		: null;
}
