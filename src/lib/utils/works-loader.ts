import type { PaginatedPaperSetResp, PaperOut } from '$lib/wire/rankless_server/responses';
import type { EntityAttsForLinks } from '$lib/wire/rankless_trees/io';
import { writable, get } from 'svelte/store';
import { browser } from '$app/environment';
import { BE_REMOTE_URL } from '$lib/constants';
import { encodeSemanticId } from '$lib/tree-functions';
import { mergeEntityAtts } from '$lib/utils/paper-helpers';
import { createStaleGuard, type IsCurrent } from '$lib/utils/stale-guard';
import { INITIAL_PAGE_SIZE, WORKS_PAGE_SIZE, WORKS_SORT } from '$lib/utils/works-paging';

export type Works = {
	papers: PaperOut[];
	entityAtts: EntityAttsForLinks;
	discAuthorNames: Record<string, string>;
};

export type WorksState = {
	semanticId: string;
	papers: PaperOut[];
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
	papers: PaperOut[];
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

// `n` of an author's works from rank `from` on.
export function worksPageUrl(base: string, semanticId: string, from: number, n: number): string {
	return `${base}/works/authors/${encodeSemanticId(semanticId)}/${from}?n=${n}&sort=${WORKS_SORT}`;
}

// Pages of works as one set, in the order given.
export function mergeWorks(...pages: Works[]): Works {
	return {
		papers: pages.flatMap((p) => p.papers),
		entityAtts: mergeEntityAtts(...pages.map((p) => p.entityAtts)),
		discAuthorNames: Object.assign({}, ...pages.map((p) => p.discAuthorNames))
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
			const resp = await fetch(worksPageUrl(BE_REMOTE_URL, semanticId, from, pageSize));
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
				...mergeWorks(s, data.resp),
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
			await fetchPage(s.sliceEnd, WORKS_PAGE_SIZE, s.semanticId);
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
				await fetchPage(s.sliceEnd, WORKS_PAGE_SIZE, s.semanticId);
			}
		} finally {
			if (stillCurrent()) store.update((s) => ({ ...s, loadingAll: false }));
		}
	}

	return { subscribe: store.subscribe, loadInitial, loadMore, loadAll };
}

export type WorksLoader = ReturnType<typeof createWorksLoader>;
