import { describe, it, expect, vi, afterEach } from 'vitest';

vi.mock('$app/environment', () => ({ browser: true }));

const { prefetchPaper, getCachedPaper } = await import('./stores');

function settled(workId: number) {
	return new Promise<Awaited<ReturnType<typeof getCachedPaper>>>((resolve) =>
		prefetchPaper(workId, resolve)
	);
}

function jsonResponse(body: unknown, ok = true, status = 200) {
	return { ok, status, json: () => Promise.resolve(body) } as Response;
}

afterEach(() => vi.unstubAllGlobals());

describe('prefetchPaper', () => {
	it('resolves works whose authorships were never matched to an author entity', async () => {
		vi.stubGlobal('fetch', () =>
			Promise.resolve(
				jsonResponse({
					title: 'Third assessment report',
					publication_year: 2002,
					doi: null,
					authorships: [{ author: { id: null, display_name: 'Australia' }, institutions: [] }]
				})
			)
		);
		const paper = await settled(3138312884);
		expect(paper?.authors).toEqual([{ name: 'Australia', link: undefined, institutions: [] }]);
		expect(getCachedPaper(3138312884)).toBe(paper);
	});

	it('settles waiters when the request fails', async () => {
		vi.stubGlobal('fetch', () => Promise.reject(new Error('network down')));
		expect(await settled(11)).toBeUndefined();
	});

	it('settles waiters on an error status', async () => {
		vi.stubGlobal('fetch', () => Promise.resolve(jsonResponse({ error: 'gone' }, false, 404)));
		expect(await settled(12)).toBeUndefined();
	});

	it('settles every waiter that queued behind one in-flight request', async () => {
		vi.stubGlobal('fetch', () => Promise.reject(new Error('network down')));
		const both = Promise.all([settled(13), settled(13)]);
		expect(await both).toEqual([undefined, undefined]);
	});

	it('settles immediately for a missing work id', async () => {
		vi.stubGlobal('fetch', () => Promise.reject(new Error('should not be called')));
		expect(await settled(0)).toBeUndefined();
	});
});
