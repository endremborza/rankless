import { describe, it, expect } from 'vitest';
import {
	formatReference,
	toBibtexFile,
	bibtexKey,
	toBibtexEntry,
	formatAuthorNames
} from './reference-format';
import type { Paper, EntityAttsForLinks } from '$lib/tree-types';

function makePaper(overrides: Partial<Paper> = {}): Paper {
	return {
		wid: 1,
		name: 'Test Paper',
		year: 2023,
		doi: '10.1234/test',
		citations: 5,
		source: 1,
		authorships: [{ author: 'F1', insts: [] }],
		isHit: false,
		...overrides
	};
}

const baseAtts: EntityAttsForLinks = {
	authors: {
		'1': { name: 'Alice Smith', semantic_id: 'alice-smith', spec_baseline: 0 },
		'2': { name: 'Bob Jones', semantic_id: 'bob-jones', spec_baseline: 0 }
	},
	sources: { '1': { name: 'Nature', semantic_id: 'nature', spec_baseline: 0 } }
};

describe('formatReference', () => {
	it('html format wraps title in DOI link and source in <em>', () => {
		const p = makePaper();
		const ref = formatReference(p, baseAtts, {}, 'html');
		expect(ref).toContain('<a href="https://doi.org/10.1234/test"');
		expect(ref).toContain('<em>Nature</em>');
		expect(ref).toContain('Smith, Alice');
		expect(ref).toContain('(2023)');
	});

	it('html format without DOI uses plain text title', () => {
		const p = makePaper({ doi: '' });
		const ref = formatReference(p, baseAtts, {}, 'html');
		expect(ref).not.toContain('<a ');
		expect(ref).toContain('Test Paper');
	});

	it('defaults to html style', () => {
		const p = makePaper();
		const ref = formatReference(p, baseAtts, {});
		expect(ref).toContain('<em>');
	});

	it('chicago format uses markdown italics', () => {
		const p = makePaper();
		const ref = formatReference(p, baseAtts, {}, 'chicago');
		expect(ref).toContain('*Nature*');
	});
});

describe('bibtex', () => {
	it('filters out Unknown authors', () => {
		const p = makePaper({
			authorships: [
				{ author: 'F1', insts: [] },
				{ author: 'F99', insts: [] } // not in entityAtts, resolves to null
			]
		});
		const bib = toBibtexEntry(p, baseAtts, {}, 'smith2023');
		expect(bib).toContain('author = {Alice Smith}');
		expect(bib).not.toContain('Unknown');
	});

	it('generates unique keys with suffixes for duplicates', () => {
		const p1 = makePaper({ wid: 1 });
		const p2 = makePaper({ wid: 2, name: 'Second Paper' });
		const p3 = makePaper({ wid: 3, name: 'Third Paper' });
		const bib = toBibtexFile([p1, p2, p3], baseAtts, {});
		expect(bib).toContain('@article{alice2023a,');
		expect(bib).toContain('@article{alice2023b,');
		expect(bib).toContain('@article{alice2023c,');
	});

	it('no suffix when key is unique', () => {
		const p1 = makePaper({ wid: 1, year: 2023 });
		const p2 = makePaper({ wid: 2, year: 2024 });
		const bib = toBibtexFile([p1, p2], baseAtts, {});
		expect(bib).toContain('@article{alice2023,');
		expect(bib).toContain('@article{alice2024,');
		expect(bib).not.toContain('alice2023a');
	});

	it('bibtexKey uses first known author last name', () => {
		expect(bibtexKey(['Alice Smith'], 2023)).toBe('alice2023');
		expect(bibtexKey([], 2023)).toBe('anon2023');
	});
});

describe('formatAuthorNames', () => {
	it('apa style with initials', () => {
		const result = formatAuthorNames(['Alice Bob Smith', 'Carol Davis'], 'apa');
		expect(result).toContain('Smith, A. B.');
		expect(result).toContain('Davis, C.');
	});

	it('mla style with "and"', () => {
		const result = formatAuthorNames(['Alice Smith', 'Bob Jones'], 'mla');
		expect(result).toContain('and');
	});
});
