/**
 * Ledger integration tests — run by pyscripts/mega_test.py.
 *
 * Two describe blocks, each selected by the Python orchestrator via --grep:
 *   "pre-pipeline"  — log in, perform user actions, verify pending state
 *   "post-pipeline" — verify the pipeline applied the actions
 *
 * State between the two phases is stored in /tmp/mega-test-ledger-state.json.
 */

import { test, expect } from '@playwright/test';
import * as fs from 'fs';

const STATE_FILE = '/tmp/mega-test-ledger-state.json';
const BE_URL = 'http://127.0.0.1:3038/v1';
const TEST_ORCID = '0000-0003-4255-0492';
const TEST_SEMANTIC_ID = 'robert-langer';
const TEST_NAME = 'Robert+Langer';

const DEV_LOGIN_URL =
	`/dev-login?orcid=${TEST_ORCID}&name=${TEST_NAME}` +
	`&semanticId=${TEST_SEMANTIC_ID}&returnTo=/authors/${TEST_SEMANTIC_ID}`;

async function login(page: import('@playwright/test').Page) {
	await page.goto(DEV_LOGIN_URL);
	await page.waitForURL(`**/authors/${TEST_SEMANTIC_ID}`);
}

async function apiPost(page: import('@playwright/test').Page, path: string, body: unknown) {
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

async function apiGet(page: import('@playwright/test').Page, path: string) {
	return page.evaluate(async (path: string) => {
		const r = await fetch(path);
		return r.json();
	}, path);
}

test.describe('pre-pipeline', () => {
	test('perform ledger actions and persist state', async ({ page }) => {
		await login(page);

		// Get the author's works from the backend.
		const worksUrl = `${BE_URL}/works/authors/${TEST_SEMANTIC_ID}/0?n=10`;
		const worksResp = await fetch(worksUrl);
		expect(worksResp.ok, `backend /works fetch failed: ${worksUrl}`).toBeTruthy();
		const worksJson = await worksResp.json();
		const papers: { wid: number; name: string; citations: number }[] =
			worksJson.resp?.papers ?? [];
		expect(papers.length, 'author must have at least 3 papers').toBeGreaterThanOrEqual(3);

		const totalPapersBefore: number = worksJson.totalPapers;
		const [p0, p1, p2] = papers;

		// Disown the first paper.
		const disown = await apiPost(page, '/api/papers/disown', { wid: p0.wid });
		expect(disown.status, 'disown should return 200').toBe(200);

		// Merge the second and third paper (higher citations → keep).
		const keepWid = p1.citations >= p2.citations ? p1.wid : p2.wid;
		const dropWid = keepWid === p1.wid ? p2.wid : p1.wid;
		const merge = await apiPost(page, '/api/papers/merge', {
			wid_keep: keepWid,
			wid_drop: dropWid
		});
		expect(merge.status, 'merge should return 200').toBe(200);

		// Verify events are recorded as pending.
		const events: { event_id: number; kind: string; revoked_at: string | null }[] =
			await apiGet(page, '/api/ledger');
		const disownEvent = events.find((e) => e.kind === 'disown_paper' && !e.revoked_at);
		const mergeEvent = events.find((e) => e.kind === 'merge_papers' && !e.revoked_at);
		expect(disownEvent, 'disown_paper event must exist').toBeDefined();
		expect(mergeEvent, 'merge_papers event must exist').toBeDefined();

		// Ledger-status should have no applied events yet (pipeline hasn't run).
		const status = await apiGet(page, '/api/ledger-status');
		expect(status.applied_event_ids?.length ?? 0, 'no events applied before pipeline').toBe(0);

		// Persist state for the post-pipeline phase.
		const state = {
			disownEventId: disownEvent!.event_id,
			mergeEventId: mergeEvent!.event_id,
			disownedWid: p0.wid,
			disownedTitle: p0.name,
			totalPapersBefore
		};
		fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));
		console.log('State written:', state);
	});
});

test.describe('post-pipeline', () => {
	test('applied manifest contains our event ids', async ({ page }) => {
		const state = JSON.parse(fs.readFileSync(STATE_FILE, 'utf-8'));
		await login(page);

		const status = await apiGet(page, '/api/ledger-status');
		expect(status.run_id, 'run_id must be set after pipeline').toBeTruthy();

		const applied: number[] = status.applied_event_ids ?? [];
		expect(
			applied,
			`disown event ${state.disownEventId} must be in applied`
		).toContain(state.disownEventId);
		expect(
			applied,
			`merge event ${state.mergeEventId} must be in applied`
		).toContain(state.mergeEventId);
	});

	test('disowned paper is absent from author works', async ({ page }) => {
		const state = JSON.parse(fs.readFileSync(STATE_FILE, 'utf-8'));
		await login(page);

		const worksUrl = `${BE_URL}/works/authors/${TEST_SEMANTIC_ID}/0?n=200`;
		const worksResp = await fetch(worksUrl);
		const worksJson = await worksResp.json();
		const papers: { name: string }[] = worksJson.resp?.papers ?? [];
		const titles = papers.map((p) => p.name);

		expect(
			titles,
			`disowned paper "${state.disownedTitle}" must not appear in works after pipeline`
		).not.toContain(state.disownedTitle);
	});

	test('author page loads and paper count decreased', async ({ page }) => {
		const state = JSON.parse(fs.readFileSync(STATE_FILE, 'utf-8'));
		await login(page);

		const worksUrl = `${BE_URL}/works/authors/${TEST_SEMANTIC_ID}/0?n=1`;
		const worksResp = await fetch(worksUrl);
		const worksJson = await worksResp.json();
		const totalPapersAfter: number = worksJson.totalPapers;

		// Disown removes one paper from the author. Merge removes the drop side.
		expect(
			totalPapersAfter,
			'paper count must be lower after disown + merge'
		).toBeLessThan(state.totalPapersBefore);
	});
});
