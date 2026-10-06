import { describe, expect, it } from 'vitest';
import { CARD_W, INNER } from '$lib/utils/cards';
import { compositeLayout, namespaceIds, parsePanelRef } from './composite';

describe('compositeLayout', () => {
	it('keeps one column at card width and stacks the panels', () => {
		const { width, slots } = compositeLayout(2, 1);
		expect(width).toBe(CARD_W);
		expect(slots[0].x).toBe(slots[1].x);
		expect(slots[1].y - slots[0].y).toBeGreaterThan(INNER.h);
	});

	it('centres a short last row and keeps every panel on the canvas', () => {
		const { width, height, slots } = compositeLayout(3, 2);
		expect(slots[2].x + INNER.w / 2).toBeCloseTo(width / 2);
		for (const s of slots) {
			expect(s.x).toBeGreaterThan(0);
			expect(s.x + INNER.w).toBeLessThan(width);
			expect(s.y + INNER.h).toBeLessThan(height);
		}
	});
});

describe('parsePanelRef', () => {
	it('reads the type, an id with slashes and escapes, the kind and the variant', () => {
		const ref = parsePanelRef('hit-papers/10.1/a%3Cb/tree?tree=1&since=2000');
		expect(ref).toMatchObject({ rootType: 'hit-papers', semanticId: '10.1/a<b', kind: 'tree' });
		expect(ref?.params.get('since')).toBe('2000');
	});

	it('reads a cohort card, which has no id', () => {
		expect(parsePanelRef('authors/table')).toMatchObject({ semanticId: '', kind: 'table' });
	});

	it('refuses a bare word and a broken escape', () => {
		expect(parsePanelRef('tree')).toBeNull();
		expect(parsePanelRef('authors/a%zz/tree')).toBeNull();
	});
});

describe('namespaceIds', () => {
	it('prefixes an id and its references, and leaves other attributes alone', () => {
		const svg = `<g grid="1"><linearGradient id="g"/><rect fill="url(#g)"/><path fill="url('#g')"/><use href="#g"/></g>`;
		expect(namespaceIds(svg, 'p0-')).toBe(
			`<g grid="1"><linearGradient id="p0-g"/><rect fill="url(#p0-g)"/><path fill="url('#p0-g')"/><use href="#p0-g"/></g>`
		);
	});
});
