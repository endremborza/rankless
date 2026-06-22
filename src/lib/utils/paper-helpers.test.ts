import { describe, it, expect } from 'vitest';
import { resolveAuthorNameOrNull, resolveAuthors, mergeEntityAtts } from './paper-helpers';
import type { Paper, EntityAttsForLinks } from '$lib/tree-types';

const atts: EntityAttsForLinks = {
	authors: { '1': { name: 'Alice Smith', semantic_id: 'alice-smith', spec_baseline: 0 } }
};

// Backend keys discAuthorNames by the full prefixed id, NOT the bare numeric id.
const disc = { D73073403: 'Carlos Navarrete' };

function makePaper(overrides: Partial<Paper> = {}): Paper {
	return {
		wid: 1,
		oaId: 0,
		name: 'Test Paper',
		year: 2023,
		doi: '',
		citations: 0,
		source: 1,
		authorships: [],
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

	it('treats the backend sentinel and empty names as null', () => {
		const d = { D1: 'Unknown', D2: '' };
		expect(resolveAuthorNameOrNull({ author: 'D1', insts: [] }, atts, d)).toBeNull();
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

	it('keeps unknown co-authors as "(unknown)" by default but drops them when skipUnknown', () => {
		const paper = makePaper({
			authorships: [
				{ author: 'F1', insts: [] },
				{ author: 'F99', insts: [] }
			]
		});
		expect(resolveAuthors(paper, atts, disc).map((a) => a.name)).toEqual([
			'Alice Smith',
			'(unknown)'
		]);
		expect(resolveAuthors(paper, atts, disc, true).map((a) => a.name)).toEqual(['Alice Smith']);
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
