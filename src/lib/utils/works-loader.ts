import { writable, get } from 'svelte/store';
import { browser } from '$app/environment';
import { BE_REMOTE_URL } from '$lib/constants';
import type { Paper, EntityAttsForLinks, PaginatedPaperSetResp } from '$lib/tree-types';
import { mergeEntityAtts } from '$lib/utils/paper-helpers';

const INITIAL_PAGE_SIZE = 20;
const MORE_PAGE_SIZE = 200;

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
// state via `$loader` and trigger fetches through `loadInitial`/`loadMore`/`loadAll`.
export function createWorksLoader() {
	const store = writable<WorksState>(emptyState(''));

	async function fetchPage(from: number, pageSize: number, semanticId: string) {
		store.update((s) => ({ ...s, loading: true }));
		let data: PaginatedPaperSetResp;
		try {
			const resp = await fetch(
				`${BE_REMOTE_URL}/works/authors/${semanticId}/${from}?n=${pageSize}`
			);
			data = await resp.json();
		} catch (e) {
			store.update((s) => ({ ...s, loading: false }));
			throw e;
		}
		store.update((s) => {
			if (s.semanticId !== semanticId) return { ...s, loading: false }; // navigated away mid-fetch
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

		store.update((s) => (s.semanticId === semanticId ? { ...s, initialLoaded: true } : s));
	}

	async function loadMore() {
		const s = get(store);
		if (!s.loading && s.sliceEnd < s.totalPapers) {
			await fetchPage(s.sliceEnd, MORE_PAGE_SIZE, s.semanticId);
		}
	}

	async function loadAll() {
		if (get(store).loadingAll) return;
		store.update((s) => ({ ...s, loadingAll: true }));
		try {
			for (;;) {
				const s = get(store);
				if (s.sliceEnd >= s.totalPapers) break;
				await fetchPage(s.sliceEnd, MORE_PAGE_SIZE, s.semanticId);
				if (get(store).semanticId !== s.semanticId) break; // navigated away
			}
		} finally {
			store.update((s) => ({ ...s, loadingAll: false }));
		}
	}

	return { subscribe: store.subscribe, loadInitial, loadMore, loadAll };
}

export type WorksLoader = ReturnType<typeof createWorksLoader>;
