import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { resolveWorkSubject, resolveAuthorSubject, ResolveError } from './id_resolver';

type FetchResp = { status: number; body?: unknown };

function mockFetch(handler: (url: string) => FetchResp) {
	return vi.fn(async (input: string | URL) => {
		const r = handler(String(input));
		return new Response(r.body !== undefined ? JSON.stringify(r.body) : null, {
			status: r.status,
			headers: { 'Content-Type': 'application/json' }
		});
	});
}

describe('resolveWorkSubject', () => {
	beforeEach(() => {
		vi.stubGlobal(
			'fetch',
			mockFetch((url) => {
				if (url.includes('wid=42')) {
					return {
						status: 200,
						body: { oaId: 999, wid: 42, doi: '10.1/foo', year: 2020, name: 'Foo et al.' }
					};
				}
				if (url.includes('oa_id=999')) {
					return {
						status: 200,
						body: { oaId: 999, wid: 42, doi: '10.1/foo', year: 2020, name: 'Foo et al.' }
					};
				}
				return { status: 404 };
			})
		);
	});
	afterEach(() => vi.unstubAllGlobals());

	it('round-trip: wid in → oa_id captured + display snapshot', async () => {
		const ws = await resolveWorkSubject({ wid: 42 });
		expect(ws.oa_id).toBe(999);
		expect(ws.doi).toBe('10.1/foo');
		expect(ws.dm_id_at_creation).toBe(42);
		expect(ws.display_snapshot.title).toBe('Foo et al.');
		expect(ws.display_snapshot.year).toBe(2020);
	});

	it('falls back to caller-supplied display when live miss', async () => {
		const ws = await resolveWorkSubject({
			oa_id: 12345,
			display_title: 'Stale Title',
			display_year: 1999
		});
		// Live lookup misses (oa_id=12345 → 404), so caller-supplied fields win
		expect(ws.oa_id).toBe(12345);
		expect(ws.display_snapshot.title).toBe('Stale Title');
		expect(ws.display_snapshot.year).toBe(1999);
	});

	it('throws ResolveError when no stable id available', async () => {
		await expect(resolveWorkSubject({})).rejects.toThrow(ResolveError);
	});
});

describe('resolveAuthorSubject', () => {
	beforeEach(() => {
		vi.stubGlobal(
			'fetch',
			mockFetch((url) => {
				if (url.includes('semantic_id=jane-doe')) {
					return {
						status: 200,
						body: {
							oaId: 5,
							dmId: 7,
							semanticId: 'jane-doe',
							orcid: '0000-0001-2345-6789',
							name: 'Jane Doe'
						}
					};
				}
				return { status: 404 };
			})
		);
	});
	afterEach(() => vi.unstubAllGlobals());

	it('round-trip: semantic_id → oa_id + orcid + display name', async () => {
		const a = await resolveAuthorSubject({ semantic_id: 'jane-doe' });
		expect(a.oa_id).toBe(5);
		expect(a.orcid).toBe('0000-0001-2345-6789');
		expect(a.semantic_id_at_creation).toBe('jane-doe');
		expect(a.display_snapshot.display_name).toBe('Jane Doe');
	});

	it('throws when neither orcid nor oa_id can be obtained', async () => {
		await expect(resolveAuthorSubject({ semantic_id: 'nobody' })).rejects.toThrow(ResolveError);
	});

	it('orcid-only input is preserved when live miss but minimum-id satisfied', async () => {
		const a = await resolveAuthorSubject({ orcid: '0000-0001-1111-1111' });
		expect(a.orcid).toBe('0000-0001-1111-1111');
		expect(a.oa_id).toBeNull();
	});
});
