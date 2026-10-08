import type { PaperOut } from '$lib/wire/rankless_server/responses';
import type { EntityAttsForLinks } from '$lib/wire/rankless_trees/io';
import { describe, it, expect } from 'vitest';
import {
	authorByline,
	hasNobelCoauthor,
	othersLabel,
	resolveAuthorNameOrNull,
	resolveAuthors,
	mergeEntityAtts,
	oaWorkToPaperResp,
	type Author
} from './paper-helpers';

const atts: EntityAttsForLinks = {
	authors: { '1': { name: 'Alice Smith', semantic_id: 'alice-smith', spec_baseline: 0 } }
};

// Backend keys discAuthorNames by the full prefixed id, NOT the bare numeric id.
const disc = { D73073403: 'Carlos Navarrete' };

function makePaper(overrides: Partial<PaperOut> = {}): PaperOut {
	const authorships = overrides.authorships ?? [];
	return {
		wid: 1,
		oaId: 0,
		name: 'Test Paper',
		year: 2023,
		doi: '',
		citations: 0,
		source: 1,
		authorCount: authorships.length,
		authorships,
		isHit: false,
		...overrides
	};
}

describe('resolveAuthorNameOrNull', () => {
	it('resolves filtered authors via the bare dm_id key', () => {
		expect(resolveAuthorNameOrNull({ author: 'F1', insts: [] }, atts, disc)).toBe('Alice Smith');
	});

	it('resolves discarded authors via the full prefixed key', () => {
		expect(resolveAuthorNameOrNull({ author: 'D73073403', insts: [] }, atts, disc)).toBe(
			'Carlos Navarrete'
		);
	});

	it('returns null for unknown ids', () => {
		expect(resolveAuthorNameOrNull({ author: 'F99', insts: [] }, atts, disc)).toBeNull();
		expect(resolveAuthorNameOrNull({ author: 'D404', insts: [] }, atts, disc)).toBeNull();
	});

	it('treats an empty name as null and any other name as a name', () => {
		const d = { D1: 'Unknown', D2: '' };
		expect(resolveAuthorNameOrNull({ author: 'D1', insts: [] }, atts, d)).toBe('Unknown');
		expect(resolveAuthorNameOrNull({ author: 'D2', insts: [] }, atts, d)).toBeNull();
	});
});

describe('resolveAuthors', () => {
	it('does not surface (unknown) for resolvable discarded co-authors', () => {
		const paper = makePaper({
			authorships: [
				{ author: 'F1', insts: [] },
				{ author: 'D73073403', insts: [] }
			]
		});
		const names = resolveAuthors(paper, atts, disc).map((a) => a.name);
		expect(names).toEqual(['Alice Smith', 'Carlos Navarrete']);
		expect(names).not.toContain('(unknown)');
	});

	it('skips served authors without a name', () => {
		const paper = makePaper({
			authorships: [
				{ author: 'F1', insts: [] },
				{ author: 'F99', insts: [] },
				{ author: 'D2', insts: [] }
			]
		});
		expect(resolveAuthors(paper, atts, { D2: '' }).map((a) => a.name)).toEqual(['Alice Smith']);
	});
});

describe('authorByline', () => {
	const named = (n: number): Author[] => Array.from({ length: n }, (_, i) => ({ name: `A${i}` }));

	it('counts every author not shown as others, unnamed and unserved ones included', () => {
		const byline = authorByline(named(3), 5, 10, false);
		expect(byline.shown.map((a) => a.name)).toEqual(['A0', 'A1', 'A2']);
		expect(byline.others).toBe(2);
		expect(byline.expandable).toBe(false);
	});

	it('caps the names and expands up to the served ones', () => {
		const capped = authorByline(named(22), 3000, 10, false);
		expect(capped.shown).toHaveLength(10);
		expect(capped.others).toBe(2990);
		expect(capped.expandable).toBe(true);

		const expanded = authorByline(named(22), 3000, 10, true);
		expect(expanded.shown).toHaveLength(22);
		expect(expanded.others).toBe(2978);
		expect(expanded.expandable).toBe(false);
	});

	it('has nothing more to show when every author is named', () => {
		expect(authorByline(named(4), 4, 10, false)).toEqual({
			shown: named(4),
			others: 0,
			expandable: false
		});
	});
});

describe('othersLabel', () => {
	it('reads "+N others" with the full count', () => {
		expect(othersLabel(1)).toBe('+1 other');
		expect(othersLabel(2990)).toBe('+2,990 others');
	});
});

describe('mergeEntityAtts', () => {
	it('deep-merges per-type records instead of clobbering', () => {
		const a: EntityAttsForLinks = {
			authors: { '1': { name: 'Alice', semantic_id: 'a', spec_baseline: 0 } }
		};
		const b: EntityAttsForLinks = {
			authors: { '2': { name: 'Bob', semantic_id: 'b', spec_baseline: 0 } }
		};
		const merged = mergeEntityAtts(a, b);
		expect(merged.authors['1'].name).toBe('Alice');
		expect(merged.authors['2'].name).toBe('Bob');
	});

	it('ignores undefined parts', () => {
		expect(mergeEntityAtts(undefined, atts).authors['1'].name).toBe('Alice Smith');
	});
});

describe('oaWorkToPaperResp', () => {
	it('keeps authorships whose author was never matched to an OpenAlex entity', () => {
		const resp = oaWorkToPaperResp({
			title: 'Third assessment report',
			doi: null,
			publication_year: 2002,
			authorships: [
				{ author: { id: null, display_name: 'Australia' }, institutions: [] },
				{
					author: { id: 'https://openalex.org/A5079108119', display_name: 'Uzbekistan' },
					institutions: [{ id: 'https://openalex.org/I1' }]
				}
			]
		});
		expect(resp.authors).toEqual([
			{ name: 'Australia', link: undefined, institutions: [] },
			{
				name: 'Uzbekistan',
				link: '/oa-id/A5079108119',
				institutions: ['https://openalex.org/I1']
			}
		]);
		expect(resp.doi).toBe('');
		expect(resp.year).toBe(2002);
	});
});

describe('hasNobelCoauthor', () => {
	const meta = {
		'1': { prize: 3, year: 2026 },
		'2': { prize: 3, year: 2026 },
		'3': { prize: 2, year: 2001 }
	};
	const by = (...ids: string[]) =>
		makePaper({ authorships: ids.map((id) => ({ author: `F${id}`, insts: [] })) });

	it('leaves out the subject and the laureates who share the subject’s prize', () => {
		expect(hasNobelCoauthor(by('1', '2'), meta, '1')).toBe(false);
		expect(hasNobelCoauthor(by('2', '3'), meta, '1')).toBe(true);
	});

	it('counts every laureate when the subject holds no prize', () => {
		expect(hasNobelCoauthor(by('2'), meta, '9')).toBe(true);
	});
});
