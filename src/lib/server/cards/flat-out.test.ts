import { METHODOLOGY } from '$lib/wire/rankless_server/responses';
import type { AttributeLabels } from '$lib/wire/rankless_trees/io';
import { describe, expect, it } from 'vitest';
import type { ResponseNode } from '$lib/tree-types';
import { loadFlatOut } from './flat-out';
import { idsParam, type CardContext } from './kind';

const node = (linkCount: number, children?: Record<number, ResponseNode>): ResponseNode => ({
	linkCount,
	sourceCount: linkCount,
	topSourceId: 1,
	topSourceLinks: 1,
	children
});
const tree = node(10, { 1: node(7), 29: node(3) });
const atts = {
	countries: {
		1: { name: 'United States', specBaseline: 0.5 },
		29: { name: 'China', specBaseline: 0.2 }
	}
} as unknown as AttributeLabels;
const { finalYear } = METHODOLOGY.workScreen;

const load = (query: string) =>
	loadFlatOut(
		{
			rootType: 'authors',
			semanticId: 'a-b',
			params: new URLSearchParams(query),
			view: null,
			fetch: (async () => new Response(JSON.stringify({ tree, atts }))) as typeof fetch
		} satisfies CardContext,
		'map',
		(inds) => inds[0],
		2000
	);

describe('map and fields cards', () => {
	it('highlight level-1 nodes of the tree and refuse any other id', async () => {
		expect((await load('hl=29')).hl).toEqual(['29']);
		await expect(load('hl=30')).rejects.toMatchObject({ status: 404 });
	});

	it('take a `since` up to the final year of the data', async () => {
		expect((await load(`since=${finalYear}`)).since).toBe(` since ${finalYear}`);
		await expect(load(`since=${finalYear + 1}`)).rejects.toMatchObject({ status: 404 });
	});
});

describe('id parameters', () => {
	it('take a hit paper id as its DOI spells it', () => {
		const doi = '10.1002/(sici)1098-1063(1996)6:4<347::aid-hipo1>3.0.co;2-i';
		expect(idsParam(new URLSearchParams({ hl: doi }), 'hl', 1)).toEqual([doi]);
	});
});
