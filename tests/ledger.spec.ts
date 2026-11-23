/**
 * Ledger integration tests — run by pyscripts/mega_test.py.
 *
 * Two describe blocks, each selected by the Python orchestrator via --grep:
 *   "pre-pipeline"  — log in, then disown, merge and claim by clicking through the works list and
 *                     the owner's panel; accept the claims, verify pending state
 *   "post-pipeline" — verify the pipeline applied the actions + restored the pinned œuvre, then
 *                     change an applied claim, claim it again, and edit one the run could not find
 *
 * State between the two phases is stored in `STATE_FILE`.
 */

import { test, expect, type Locator, type Page } from '@playwright/test';
import * as fs from 'fs';
import dev from '../src/lib/assets/data/dev.json' with { type: 'json' };
import type { LedgerEvent } from '../src/lib/types/ledger';
import {
	ACTION_LABELS,
	COMPOSE_COPY,
	EVENT_LABELS,
	NOT_IN_DATA,
	PANEL_SECTIONS,
	REPLACE_COPY,
	UNDO_PENDING,
	WORKS_ACTIONS
} from '../src/lib/utils/ledger-display';
import { AWAITING_REVIEW, skippedStatus } from '../src/lib/utils/ledger-status';
import { WORKS_PAGE_SIZE } from '../src/lib/utils/works-paging';
import { BE_URL } from './helpers';

const STATE_FILE = '/tmp/mega-test-ledger-state.json';
const TEST_ORCID = dev.testOrcid;
const TEST_SEMANTIC_ID = 'robert-langer';
const TEST_NAME = 'Robert+Langer';
// A DOI no snapshot holds: the run skips its claim, which the panel then offers to edit.
const ABSENT_DOI = '10.5555/rankless-mega-test-absent';
const CLAIM_FORM = COMPOSE_COPY.claim_paper;
// An owner's page loads every work before it offers the row actions.
const OWNER_READY_MS = 60_000;

test.setTimeout(2 * OWNER_READY_MS);

const DEV_LOGIN_URL =
	`/dev-login?orcid=${TEST_ORCID}&name=${TEST_NAME}` +
	`&semanticId=${TEST_SEMANTIC_ID}&returnTo=/authors/${TEST_SEMANTIC_ID}`;

type Paper = { wid: number; name: string; citations: number; doi: string };

type State = {
	disownKey: string;
	mergeKey: string;
	claimKey: string;
	orphanKey: string;
	claimDoi: string;
	changeDoi: string;
	editDoi: string;
	disownedTitle: string;
	totalPapersBefore: number;
};

const readState = (): State => JSON.parse(fs.readFileSync(STATE_FILE, 'utf-8'));

async function login(page: Page) {
	await page.goto(DEV_LOGIN_URL);
	await page.waitForURL(`**/authors/${TEST_SEMANTIC_ID}`);
}

async function apiPost(page: Page, path: string, body: unknown) {
	return page.evaluate(
		async ({ path, body }: { path: string; body: unknown }) => {
			const r = await fetch(path, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(body)
			});
			return { status: r.status, body: await r.json() };
		},
		{ path, body }
	);
}

async function apiGet(page: Page, path: string) {
	return page.evaluate(async (path: string) => {
		const r = await fetch(path);
		return r.json();
	}, path);
}

const ownEvents = (page: Page): Promise<LedgerEvent[]> => apiGet(page, '/api/ledger');

const isActive = (e: LedgerEvent, kind: LedgerEvent['kind']) => e.kind === kind && !e.revoked_at;

const activeClaim = (events: LedgerEvent[], doi: string) =>
	events.find(
		(e) =>
			isActive(e, 'claim_paper') && e.payload.kind === 'claim_paper' && e.payload.work.doi === doi
	);

// The works-list row of a paper, found by its DOI link.
const workRow = (page: Page, doi: string) =>
	page
		.locator('#works tbody tr', { has: page.locator(`a[href="https://doi.org/${doi}"]`) })
		.first();

const panel = (page: Page) => page.locator('.ledger-panel');

// The row actions are drawn in the browser once every work is loaded, so they also mark the page
// as hydrated: a click before that reaches no handler.
async function ownerReady(page: Page) {
	const remove = page
		.locator('#works tbody')
		.getByRole('button', { name: WORKS_ACTIONS.remove })
		.first();
	await expect(remove, 'owner row actions must appear').toBeVisible({ timeout: OWNER_READY_MS });
}

// One of the panel's two lists, by its heading.
const panelList = (page: Page, section: keyof typeof PANEL_SECTIONS) =>
	panel(page)
		.locator('.item-list')
		.filter({ has: page.locator('h4', { hasText: PANEL_SECTIONS[section] }) });

const activeUndo = (events: LedgerEvent[], key: string) =>
	events.some(
		(e) => isActive(e, 'revoke') && e.payload.kind === 'revoke' && e.payload.target_key === key
	);

async function claimByDoi(page: Page, doi: string) {
	await panel(page).getByPlaceholder(CLAIM_FORM.identifier).fill(doi);
	await panel(page).getByRole('button', { name: CLAIM_FORM.submitLabel, exact: true }).click();
	await expect(panel(page).getByText(CLAIM_FORM.doneText, { exact: true })).toBeVisible();
}

// Opens a row's form, checks it carries the identifier the event has, and saves another.
async function replaceIdentifier(
	page: Page,
	row: Locator,
	action: 'change' | 'edit',
	from: string,
	to: string
) {
	await row.getByRole('button', { name: ACTION_LABELS[action] }).click();
	const form = panel(page).locator('.row-form');
	const input = form.getByPlaceholder(CLAIM_FORM.identifier);
	await expect(input).toHaveValue(from);
	await input.fill(to);
	await form.getByRole('button', { name: REPLACE_COPY.submitLabel }).click();
}

test.describe('pre-pipeline', () => {
	test('perform ledger actions and persist state', async ({ page }) => {
		await login(page);

		// The author's works with a DOI, from the backend: a DOI names a paper's row and its claim.
		const worksUrl = `${BE_URL}/works/authors/${TEST_SEMANTIC_ID}/0?n=30`;
		const worksResp = await fetch(worksUrl);
		expect(worksResp.ok, `backend /works fetch failed: ${worksUrl}`).toBeTruthy();
		const worksJson = await worksResp.json();
		const papers = (worksJson.resp?.papers ?? []).filter((p: Paper) => p.doi) as Paper[];
		expect(papers.length, 'author must have at least 6 papers with a DOI').toBeGreaterThanOrEqual(
			6
		);

		const totalPapersBefore: number = worksJson.totalPapers;
		const [p0, p1, p2, claimed, changeTo, editTo] = papers;

		// Disown the first paper from its row.
		await ownerReady(page);
		await workRow(page, p0.doi).getByRole('button', { name: WORKS_ACTIONS.remove }).click();

		// Merge the second and third paper; the list keeps the more cited one by default.
		const keepWid = p1.citations >= p2.citations ? p1.wid : p2.wid;
		for (const p of [p1, p2])
			await workRow(page, p.doi).getByLabel(WORKS_ACTIONS.selectForMerge).check();
		await expect(page.locator('.merge-rep select')).toHaveValue(String(keepWid));
		await page.getByRole('button', { name: WORKS_ACTIONS.mergeInto(1) }).click();

		// Claim an untouched paper by its DOI in the panel's form.
		await claimByDoi(page, claimed.doi);

		// Skip-only case, posted directly: a claim on a DOI the snapshot does not hold.
		const orphan = await apiPost(page, '/api/ledger', { kind: 'claim_paper', doi: ABSENT_DOI });
		expect(orphan.status, 'orphan claim should return 200').toBe(200);

		// The panel lists the three clicked events as pending, by the titles the page serves.
		const pending = panelList(page, 'pending').locator('.item-row');
		await expect(pending.filter({ hasText: EVENT_LABELS.disown_paper })).toHaveCount(1);
		await expect(pending.filter({ hasText: EVENT_LABELS.merge_papers })).toHaveCount(1);
		await expect(pending.filter({ hasText: EVENT_LABELS.claim_paper })).toContainText(
			AWAITING_REVIEW
		);

		const events = await ownEvents(page);
		const disownEvent = events.find((e) => isActive(e, 'disown_paper'));
		const mergeEvent = events.find((e) => isActive(e, 'merge_papers'));
		const claimEvent = activeClaim(events, claimed.doi);
		const orphanEvent = activeClaim(events, ABSENT_DOI);
		expect(disownEvent, 'disown_paper event must exist').toBeDefined();
		expect(mergeEvent, 'merge_papers event must exist').toBeDefined();
		expect(claimEvent, 'claim_paper event must exist').toBeDefined();
		expect(orphanEvent, 'orphan claim_paper event must exist').toBeDefined();
		expect(
			mergeEvent!.payload.kind === 'merge_papers' && mergeEvent!.payload.keep.dm_id_at_creation,
			'the merge must keep the more cited paper'
		).toBe(keepWid);

		// Claims default to pending_review and only accepted events reach the pipeline;
		// the dev-login user is in ADMIN_ORCIDS (set by mega_test.py), so accept them here.
		const moderate = await apiPost(page, '/api/admin/moderate', {
			event_ids: [claimEvent!.event_id, orphanEvent!.event_id],
			decision: 'accepted'
		});
		expect(moderate.status, 'claim moderation should return 200').toBe(200);

		// The from-snapshot build already applies the curated ledger; only our events must be pending.
		const status = await apiGet(page, '/api/ledger-status');
		const applied: string[] = status.applied_keys ?? [];
		for (const e of [disownEvent!, mergeEvent!, claimEvent!, orphanEvent!])
			expect(applied, `${e.kind} must not be applied before pipeline`).not.toContain(e.key);

		// Persist state for the post-pipeline phase. Events are matched by their merge-stable
		// logical key, not event_id (which the deploy's DB merge renumbers).
		const state: State = {
			disownKey: disownEvent!.key,
			mergeKey: mergeEvent!.key,
			claimKey: claimEvent!.key,
			orphanKey: orphanEvent!.key,
			claimDoi: claimed.doi,
			changeDoi: changeTo.doi,
			editDoi: editTo.doi,
			disownedTitle: p0.name,
			totalPapersBefore
		};
		fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
		console.log('State written:', state);
	});
});

test.describe('post-pipeline', () => {
	test('applied manifest contains our event ids', async ({ page }) => {
		const state = readState();
		await login(page);

		const status = await apiGet(page, '/api/ledger-status');
		expect(status.run_id, 'run_id must be set after pipeline').toBeTruthy();

		const applied: string[] = status.applied_keys ?? [];
		expect(applied, `disown ${state.disownKey} must be in applied`).toContain(state.disownKey);
		expect(applied, `merge ${state.mergeKey} must be in applied`).toContain(state.mergeKey);
		expect(applied, `claim ${state.claimKey} must be in applied`).toContain(state.claimKey);
	});

	test('disowned paper is absent from author works', async ({ page }) => {
		const state = readState();
		await login(page);

		const worksUrl = `${BE_URL}/works/authors/${TEST_SEMANTIC_ID}/0?n=${WORKS_PAGE_SIZE}`;
		const worksResp = await fetch(worksUrl);
		const worksJson = await worksResp.json();
		const papers: { name: string }[] = worksJson.resp?.papers ?? [];
		const titles = papers.map((p) => p.name);

		expect(
			titles,
			`disowned paper "${state.disownedTitle}" must not appear in works after pipeline`
		).not.toContain(state.disownedTitle);
	});

	test('author page loads and the pinned œuvre is restored', async ({ page }) => {
		const state = readState();
		await login(page);

		const worksUrl = `${BE_URL}/works/authors/${TEST_SEMANTIC_ID}/0?n=1`;
		const worksResp = await fetch(worksUrl);
		const worksJson = await worksResp.json();
		const totalPapersAfter: number = worksJson.totalPapers;

		// Logging in pinned the author as an owner, so the pipeline forces their full
		// œuvre through the type/citation screens — that restoration dwarfs the two
		// papers the disown + merge removed (whose absence test 2 checks by title).
		expect(
			totalPapersAfter,
			'pinned œuvre restoration must raise the served paper count'
		).toBeGreaterThan(state.totalPapersBefore);
	});

	test('changing an applied claim revokes it, and claiming it again withdraws the undo', async ({
		page
	}) => {
		const state = readState();
		await login(page);

		await ownerReady(page);
		const claimRow = panelList(page, 'applied').locator('.item-row', {
			hasText: EVENT_LABELS.claim_paper
		});
		await replaceIdentifier(page, claimRow, 'change', state.claimDoi, state.changeDoi);
		await expect(claimRow).toContainText(UNDO_PENDING);

		const events = await ownEvents(page);
		const applied = events.find((e) => e.key === state.claimKey)!;
		expect(applied.revoked_at, 'an applied event stays in the log untouched').toBeNull();
		expect(activeUndo(events, state.claimKey), 'the applied claim must have a pending revoke').toBe(
			true
		);
		expect(activeClaim(events, state.changeDoi), 'the replacement claim must exist').toBeDefined();

		const withdrawal = await page.evaluate(
			(id: number) => fetch(`/api/ledger/${id}`, { method: 'DELETE' }).then((r) => r.status),
			applied.event_id
		);
		expect(withdrawal, 'an applied event cannot be withdrawn').toBe(409);

		await claimByDoi(page, state.claimDoi);
		await expect(claimRow).not.toContainText(UNDO_PENDING);
		expect(
			activeUndo(await ownEvents(page), state.claimKey),
			'claiming an undone paper again must withdraw its undo'
		).toBe(false);
	});

	test('editing a claim the run could not find withdraws it for the corrected one', async ({
		page
	}) => {
		const state = readState();
		await login(page);

		await ownerReady(page);
		const orphanRow = panelList(page, 'pending').locator('.item-row', { hasText: ABSENT_DOI });
		await expect(orphanRow).toContainText(skippedStatus('doi_not_in_snapshot'));
		await expect(orphanRow).toContainText(NOT_IN_DATA);
		await replaceIdentifier(page, orphanRow, 'edit', ABSENT_DOI, state.editDoi);
		await expect(orphanRow).toHaveCount(0);

		const events = await ownEvents(page);
		expect(
			events.find((e) => e.key === state.orphanKey && e.kind === 'claim_paper')?.revoked_at,
			'the orphan claim must be withdrawn'
		).toBeTruthy();
		expect(activeClaim(events, state.editDoi), 'the corrected claim must exist').toBeDefined();
	});
});
