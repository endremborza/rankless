import { describe, expect, it } from 'vitest';
import type { PaperOut } from '$lib/wire/rankless_server/responses';
import type { ImpactHighlightsResp } from '$lib/wire/rankless_server/highlights';
import {
	byCiterOrder,
	citedLayer,
	highlightsView,
	marks,
	multipleLabel,
	ownCard,
	type PaperRow
} from './impact-highlights';

const paper = (wid: number, source: number, isHit = false): PaperOut =>
	({
		wid,
		source,
		isHit,
		name: `p${wid}`,
		year: 2020,
		citations: 10,
		authorCount: 3,
		authorships: []
	}) as never;

const label = (name: string, semantic_id: string) => ({ name, semantic_id }) as never;

const resp: ImpactHighlightsResp = {
	highlights: [
		{
			wid: 1,
			cites: [3, 2],
			badges: [
				{ kind: 'apex', source: 7, rank: 1, rarity: 0.1 },
				{ kind: 'laureate', author: 9, rarity: 0.05 },
				{ kind: 'institution', institution: 4, country: 5, papers: 12, rank: 1, rarity: 0.2 }
			]
		},
		{ wid: 2, cites: [3], badges: [{ kind: 'hit', multiple: 4.44, rarity: 0.3 }] },
		{ wid: 99, cites: [2], badges: [] }
	],
	totals: {
		citingPapers: 50,
		independent: 20,
		hits: 1,
		apex: 3,
		laureates: 1,
		stars: 0,
		institutions: 2
	},
	papers: {
		papers: [paper(1, 7), paper(2, 0, true), paper(3, 7, true)],
		entityAtts: {
			sources: { '7': label('Nature', 'nature') },
			authors: { '9': label('Ada Laureate', 'ada-laureate') },
			institutions: { '4': label('Harvard University', 'harvard') }
		},
		discAuthorNames: {},
		authorsMeta: {}
	},
	apexSources: [7]
};

describe('highlightsView', () => {
	const [first, second, ...rest] = highlightsView(resp);

	it('resolves the citing papers in pick order, skipping a paper the response lacks', () => {
		expect([first, second, ...rest].map((r) => r.paper.wid)).toEqual([1, 2]);
		expect(first.cites.map((p) => p.wid)).toEqual([3, 2]);
	});

	it('marks the journal, the laureate in place of the first author, and the institution', () => {
		expect(first.facts).toEqual([
			{ label: 'Nature', href: '/sources/nature', kind: 'apex' },
			{ label: '10 citations', title: undefined, kind: undefined }
		]);
		expect(first.people).toEqual([
			{
				label: 'Ada Laureate',
				href: '/authors/ada-laureate',
				kind: 'laureate',
				title: 'Nobel laureate'
			}
		]);
		expect(first.others).toBe(2);
		expect(first.institutions).toEqual([
			{
				label: 'Harvard University',
				href: '/institutions/harvard',
				kind: 'institution',
				title: '12 independent citing papers'
			}
		]);
	});

	it("marks a hit's citations with its multiple", () => {
		expect(marks(second)).toEqual([
			{
				label: '10 citations',
				title: `${multipleLabel(4.44)} the bar of its field and year`,
				kind: 'hit'
			}
		]);
	});
});

describe('ownCard', () => {
	it('marks an apex journal and a hit', () => {
		const card = ownCard(paper(3, 7, true), resp);
		expect(marks(card).map((m) => m.kind)).toEqual(['apex', 'hit']);
	});

	it('leaves a journal outside the apex pool unmarked', () => {
		expect(marks(ownCard(paper(2, 0, true), resp)).map((m) => m.kind)).toEqual(['hit']);
	});
});

describe('multipleLabel', () => {
	it('keeps one decimal below ten', () => {
		expect(multipleLabel(4.44)).toBe('4.4×');
		expect(multipleLabel(12.6)).toBe('13×');
	});
});

describe('citedLayer', () => {
	const row = (...wids: number[]): Pick<PaperRow, 'cites'> => ({
		cites: wids.map((w) => paper(w, 0))
	});

	it('gives every row a cited paper, preferring the shared ones, and links every citer', () => {
		const layer = citedLayer([row(1, 2), row(2), row(3)], 2);
		expect(layer.papers.map((p) => p.wid)).toEqual([2, 3]);
		expect(layer.links).toEqual([
			[0, 0],
			[1, 0],
			[2, 1]
		]);
	});

	it('fills up to the cap with the rest', () => {
		expect(citedLayer([row(1, 2)], 2).papers.map((p) => p.wid)).toEqual([1, 2]);
	});
});

describe('byCiterOrder', () => {
	it('orders the papers under their citers and remaps the links', () => {
		const ordered = byCiterOrder({
			papers: [paper(1, 0), paper(2, 0)],
			links: [
				[1, 0],
				[0, 1]
			]
		});
		expect(ordered.papers.map((p) => p.wid)).toEqual([2, 1]);
		expect(ordered.links).toEqual([
			[1, 1],
			[0, 0]
		]);
	});
});
