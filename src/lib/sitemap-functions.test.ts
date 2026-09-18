import { describe, it, expect, vi, afterEach } from 'vitest';
import { respsFromLinks } from './sitemap-functions';
import type { RootType, SliceResp, TableRow } from './tree-types';

function row(semanticId: string): TableRow {
	return {
		name: semanticId,
		semanticId,
		papers: 1,
		citations: 1,
		oaId: 1,
		dmId: 1,
		rank: 1,
		values: {}
	};
}

function stubSlice(resp: SliceResp) {
	vi.stubGlobal(
		'fetch',
		vi.fn(async () => ({ json: async () => resp }))
	);
}

afterEach(() => vi.unstubAllGlobals());

describe('respsFromLinks', () => {
	it('reads the rows of a slice page, drops non-ascii ids and tags the root type', async () => {
		stubSlice({
			rows: [row('ada-lovelace'), row('erdős-pál')],
			meta: { total: 2, screened: null, columns: ['citations'] }
		});
		const links = [{ url: 'http://be/v1/slice/authors/0/2', name: 'authors' as RootType }];
		const out = await respsFromLinks(links);
		expect(out.map((e) => e.semanticId)).toEqual(['ada-lovelace']);
		expect(out[0].rootType).toBe('authors');
	});
});
