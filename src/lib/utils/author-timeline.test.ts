import { describe, it, expect } from 'vitest';
import { buildCoauthors, sortCoauthors, coauthorYearDomain, makeTicks } from './author-timeline';
import type { Paper, EntityAttsForLinks } from '$lib/tree-types';

const atts: EntityAttsForLinks = {
	authors: {
		'1': { name: 'Hero Author', semantic_id: 'hero', spec_baseline: 0 },
		'2': { name: 'Alice Smith', semantic_id: 'alice-smith', spec_baseline: 0 }
	}
};
const disc = { D9: 'Carlos Navarrete' };

function makePaper(overrides: Partial<Paper> = {}): Paper {
	return {
		wid: 1,
		oaId: 0,
		name: 'Test Paper',
		year: 2020,
		doi: '',
		citations: 0,
		source: 1,
		authorships: [],
		isHit: false,
		...overrides
	};
}

describe('buildCoauthors', () => {
	const papers = [
		makePaper({
			wid: 1,
			year: 2019,
			authorships: [
				{ author: 'F1', insts: [] },
				{ author: 'F2', insts: [] }
			]
		}),
		makePaper({
			wid: 2,
			year: 2021,
			isHit: true,
			authorships: [
				{ author: 'F1', insts: [] },
				{ author: 'F2', insts: [] },
				{ author: 'D9', insts: [] }
			]
		}),
		makePaper({
			wid: 3,
			year: 2021,
			authorships: [
				{ author: 'F1', insts: [] },
				{ author: 'F2', insts: [] }
			]
		})
	];

	it('excludes the hero and keeps every other named co-author', () => {
		const cs = buildCoauthors(papers, atts, disc, 'hero');
		expect(cs.map((c) => c.key).sort()).toEqual(['D9', 'F2']);
	});

	it('links filtered authors and leaves discarded ones unlinked', () => {
		const cs = buildCoauthors(papers, atts, disc, 'hero');
		const alice = cs.find((c) => c.key === 'F2')!;
		const carlos = cs.find((c) => c.key === 'D9')!;
		expect(alice.url).toBe('/authors/alice-smith');
		expect(carlos.name).toBe('Carlos Navarrete');
		expect(carlos.url).toBeNull();
	});

	it('groups shared papers by year and counts hits', () => {
		const alice = buildCoauthors(papers, atts, disc, 'hero').find((c) => c.key === 'F2')!;
		expect(alice.count).toBe(3);
		expect(alice.hitCount).toBe(1);
		expect(alice.firstYear).toBe(2019);
		expect(alice.lastYear).toBe(2021);
		expect(alice.groups.map((g) => [g.year, g.papers.length, g.hasHit])).toEqual([
			[2019, 1, false],
			[2021, 2, true]
		]);
	});

	it('skips papers without a usable year and unresolvable authors', () => {
		const noisy = [
			makePaper({ wid: 4, year: 0, authorships: [{ author: 'F2', insts: [] }] }),
			makePaper({ wid: 5, year: 2022, authorships: [{ author: 'F404', insts: [] }] })
		];
		expect(buildCoauthors(noisy, atts, disc, 'hero')).toEqual([]);
	});
});

describe('sortCoauthors', () => {
	const cs = buildCoauthors(
		[
			makePaper({ wid: 1, year: 2010, authorships: [{ author: 'F2', insts: [] }] }),
			makePaper({ wid: 2, year: 2023, authorships: [{ author: 'D9', insts: [] }] }),
			makePaper({ wid: 3, year: 2024, authorships: [{ author: 'D9', insts: [] }] })
		],
		atts,
		disc,
		'hero'
	);

	it('orders by first collaboration, recency, and share count', () => {
		expect(sortCoauthors(cs, 'first').map((c) => c.key)).toEqual(['F2', 'D9']);
		expect(sortCoauthors(cs, 'recent').map((c) => c.key)).toEqual(['D9', 'F2']);
		expect(sortCoauthors(cs, 'count').map((c) => c.key)).toEqual(['D9', 'F2']);
	});
});

describe('coauthorYearDomain', () => {
	it('spans the shown co-authors first/last years', () => {
		const cs = buildCoauthors(
			[
				makePaper({ wid: 1, year: 2005, authorships: [{ author: 'F2', insts: [] }] }),
				makePaper({ wid: 2, year: 2018, authorships: [{ author: 'F2', insts: [] }] })
			],
			atts,
			disc,
			'hero'
		);
		expect(coauthorYearDomain(cs)).toEqual({ lo: 2005, hi: 2018, span: 13 });
	});

	it('ignores hero-only years outside the shown co-authors range', () => {
		// Hero publishes 1990–2024, but the only shown co-author collaborated 2010–2012.
		const cs = buildCoauthors(
			[
				makePaper({ wid: 1, year: 1990, authorships: [{ author: 'F1', insts: [] }] }),
				makePaper({ wid: 2, year: 2010, authorships: [{ author: 'F2', insts: [] }] }),
				makePaper({ wid: 3, year: 2012, authorships: [{ author: 'F2', insts: [] }] }),
				makePaper({ wid: 4, year: 2024, authorships: [{ author: 'F1', insts: [] }] })
			],
			atts,
			disc,
			'hero'
		);
		expect(coauthorYearDomain(cs)).toEqual({ lo: 2010, hi: 2012, span: 2 });
	});

	it('falls back to a unit span when no co-authors are shown', () => {
		expect(coauthorYearDomain([])).toEqual({ lo: 0, hi: 0, span: 1 });
	});
});

describe('makeTicks', () => {
	it('produces round, in-range year ticks', () => {
		const ticks = makeTicks({ lo: 2001, hi: 2024, span: 23 }, 5);
		expect(ticks).toEqual([2005, 2010, 2015, 2020]);
		expect(ticks.every((t) => t >= 2001 && t <= 2024)).toBe(true);
	});

	it('returns a single tick for a zero-width domain', () => {
		expect(makeTicks({ lo: 2010, hi: 2010, span: 1 }, 5)).toEqual([2010]);
	});
});
