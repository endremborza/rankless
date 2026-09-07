import { describe, it, expect, vi, afterEach } from 'vitest';
import { get } from 'svelte/store';
import type { PaginatedPaperSetResp } from '$lib/tree-types';
import { createWorksLoader } from './works-loader';

vi.mock(import('$app/environment'), async (importOriginal) => ({
	...(await importOriginal()),
	browser: true
}));

type Deferred = { resolve: (page: PaginatedPaperSetResp) => void };

function fakeFetch() {
	const calls: Deferred[] = [];
	vi.stubGlobal(
		'fetch',
		vi.fn(
			() =>
				new Promise<{ json: () => Promise<PaginatedPaperSetResp> }>((resolve) =>
					calls.push({ resolve: (page) => resolve({ json: async () => page }) })
				)
		)
	);
	return calls;
}

function page(wid: string): PaginatedPaperSetResp {
	return {
		sliceStart: 0,
		totalPapers: 5,
		resp: { papers: [{ wid }], entityAtts: {}, discAuthorNames: {} }
	} as unknown as PaginatedPaperSetResp;
}

afterEach(() => vi.unstubAllGlobals());

describe('createWorksLoader', () => {
	it('drops a page fetched for a seed that was superseded meanwhile', async () => {
		const calls = fakeFetch();
		const works = createWorksLoader();
		const staleA = works.loadInitial('A');
		const b = works.loadInitial('B');
		const freshA = works.loadInitial('A');
		expect(calls).toHaveLength(3);

		calls[0].resolve(page('stale'));
		await staleA;
		expect(get(works)).toMatchObject({ semanticId: 'A', papers: [], initialLoaded: false });

		calls[2].resolve(page('fresh'));
		await freshA;
		expect(get(works)).toMatchObject({
			semanticId: 'A',
			papers: [{ wid: 'fresh' }],
			initialLoaded: true,
			loading: false
		});

		calls[1].resolve(page('b'));
		await b;
		expect(get(works).papers).toEqual([{ wid: 'fresh' }]);
	});
});
