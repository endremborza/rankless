import { writable, get } from 'svelte/store';
import { browser } from '$app/environment';
import { BE_REMOTE_URL } from '$lib/constants';
import type { Paper, EntityAttsForLinks, PaginatedPaperSetResp } from '$lib/tree-types';
import { mergeEntityAtts } from '$lib/utils/paper-helpers';
import { createStaleGuard, type IsCurrent } from '$lib/utils/stale-guard';

const INITIAL_PAGE_SIZE = 20;
const MORE_PAGE_SIZE = 200;
// Pages arrive ranked by citation count so the first screen is the entity's most-cited works and
// every appended page stays contiguous in that order (the backend re-sorts deterministically).
const WORKS_SORT = 'citations';

export type WorksState = {
	semanticId: string;
	papers: Paper[];
	entityAtts: EntityAttsForLinks;
	discAuthorNames: Record<string, string>;
	sliceEnd: number;
	totalPapers: number;
	loading: boolean;
	loadingAll: boolean;
	initialLoaded: boolean;
	allLoaded: boolean;
};

// SSR-provided first batch — lets the initial render skip a client round-trip.
export type WorksSeed = {
	papers: Paper[];
	entityAtts: EntityAttsForLinks;
	discAuthorNames: Record<string, string>;
	sliceEnd: number;
	totalPapers: number;
};

function emptyState(semanticId: string): WorksState {
	return {
		semanticId,
		papers: [],
		entityAtts: {},
		discAuthorNames: {},
		sliceEnd: 0,
		totalPapers: 0,
		loading: false,
		loadingAll: false,
		initialLoaded: false,
		allLoaded: false
	};
}

function reachedEnd(sliceEnd: number, totalPapers: number): boolean {
	return totalPapers > 0 ? sliceEnd >= totalPapers : true;
}

// Shared, paginated loader for an author's works. One instance per entity page feeds both the
// works table and the co-author network, so every page is fetched at most once. Consumers read
// state via `$loader` and trigger fetches through `loadInitial`/`loadMore`/`loadAll`. Every reseed
// claims the guard, so a page still in flight for a previous seed is dropped on arrival.
export function createWorksLoader() {
	const store = writable<WorksState>(emptyState(''));
	const claim = createStaleGuard();
	let isCurrent: IsCurrent = claim();

	async function fetchPage(from: number, pageSize: number, semanticId: string) {
		const stillCurrent = isCurrent;
		store.update((s) => ({ ...s, loading: true }));
		let data: PaginatedPaperSetResp;
		try {
			const resp = await fetch(
				`${BE_REMOTE_URL}/works/authors/${semanticId}/${from}?n=${pageSize}&sort=${WORKS_SORT}`
			);
			data = await resp.json();
		} catch (e) {
			if (stillCurrent()) store.update((s) => ({ ...s, loading: false }));
			throw e;
		}
		if (!stillCurrent()) return;
		store.update((s) => {
			const sliceEnd = data.sliceStart + data.resp.papers.length;
			return {
				...s,
				papers: [...s.papers, ...data.resp.papers],
				entityAtts: mergeEntityAtts(s.entityAtts, data.resp.entityAtts),
				discAuthorNames: { ...s.discAuthorNames, ...data.resp.discAuthorNames },
				sliceEnd,
				totalPapers: data.totalPapers,
				loading: false,
				allLoaded: reachedEnd(sliceEnd, data.totalPapers)
			};
		});
	}

	async function loadInitial(semanticId: string, seed?: WorksSeed) {
		const cur = get(store);
		if (cur.semanticId === semanticId && cur.initialLoaded) return;
		isCurrent = claim();
		const stillCurrent = isCurrent;

		if (seed && seed.papers.length > 0) {
			store.set({
				...emptyState(semanticId),
				papers: seed.papers,
				entityAtts: seed.entityAtts,
				discAuthorNames: seed.discAuthorNames,
				sliceEnd: seed.sliceEnd,
				totalPapers: seed.totalPapers,
				allLoaded: reachedEnd(seed.sliceEnd, seed.totalPapers)
			});
		} else {
			store.set(emptyState(semanticId));
			if (browser) await fetchPage(0, INITIAL_PAGE_SIZE, semanticId);
		}

		if (stillCurrent()) store.update((s) => ({ ...s, initialLoaded: true }));
	}

	async function loadMore() {
		const s = get(store);
		if (!s.loading && s.sliceEnd < s.totalPapers) {
			await fetchPage(s.sliceEnd, MORE_PAGE_SIZE, s.semanticId);
		}
	}

	async function loadAll() {
		if (get(store).loadingAll) return;
		const stillCurrent = isCurrent;
		store.update((s) => ({ ...s, loadingAll: true }));
		try {
			while (stillCurrent()) {
				const s = get(store);
				if (s.sliceEnd >= s.totalPapers) break;
				await fetchPage(s.sliceEnd, MORE_PAGE_SIZE, s.semanticId);
			}
		} finally {
			if (stillCurrent()) store.update((s) => ({ ...s, loadingAll: false }));
		}
	}

	return { subscribe: store.subscribe, loadInitial, loadMore, loadAll };
}

export type WorksLoader = ReturnType<typeof createWorksLoader>;
