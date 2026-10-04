import { describe, expect, it } from 'vitest';
import type { RelatedEntity } from '$lib/tree-types';
import { getIndex } from '$lib/network-util';
import { INNER } from '$lib/utils/cards';
import { overlaps } from '$lib/utils/label-placement';
import { layoutNetwork } from './network';

const N = 25;
const authors: RelatedEntity[] = Array.from({ length: N }, (_, i) => ({
	name: `Firstname Longsurname${i}`,
	semanticId: `a-${i}`,
	etype: 'authors',
	score: N - i,
	count: N - i
}));

describe('layoutNetwork', () => {
	it('keeps labels apart and inside the card, always labelling a highlighted node', () => {
		const { nodes } = layoutNetwork(authors, N, [], new Set(['a-20']));
		const boxes = nodes.flatMap((n) => (n.label ? [n.label.box] : []));
		expect(nodes[20].label?.text).toBe('Firstname Longsurname20 · 5');
		expect(nodes[0].label?.text).toBe('Firstname Longsurname0');
		for (const [i, a] of boxes.entries()) {
			expect(a.x).toBeGreaterThanOrEqual(0);
			expect(a.x + a.w).toBeLessThanOrEqual(INNER.w);
			for (const b of boxes.slice(i + 1)) expect(overlaps(a, b)).toBe(false);
		}
	});

	it('reads edge weights by the full node count when showing the first n', () => {
		const weights = new Array((N * (N - 1)) / 2).fill(0);
		weights[getIndex(1, 3, N)] = 4;
		weights[getIndex(2, 20, N)] = 9;
		const { edges } = layoutNetwork(authors.slice(0, 5), N, weights, new Set(['a-3']));
		expect(edges).toHaveLength(1);
		expect(edges[0]).toMatchObject({ rate: 1, on: true });
	});
});
