import { describe, it, expect } from 'vitest';
import { computeSeen, buildSubgraphs, classifyComponentLayers } from './dag-builder';
import type { RefTree } from '$lib/tree-types';

const leaf: RefTree = 'Leaf';
const node = (children: Record<number, RefTree>): RefTree => ({ Node: children });

function pm(...wids: [number, number][]): Record<number, { year: number }> {
	const m: Record<number, { year: number }> = {};
	for (const [w, y] of wids) m[w] = { year: y };
	return m;
}

describe('computeSeen', () => {
	it('single direct edge', () => {
		const dag = node({ 1: node({ 2: leaf }) });
		const seen = computeSeen(dag);
		expect(seen[1].children.has(2)).toBe(true);
		expect(seen[2].parents.has(1)).toBe(true);
	});

	it('direct path order: short path first then once-removed — edge not lost', () => {
		const dag = node({
			2: node({ 100: leaf }),
			10: node({ 9: node({ 100: leaf }) })
		});
		const seen = computeSeen(dag);

		expect(seen[9].children.has(100)).toBe(true);
		expect(seen[100].parents.has(9)).toBe(true);
		expect(seen[100].parents.has(2)).toBe(true);
		expect(seen[2].children.has(100)).toBe(true);
		expect(seen[10].children.has(9)).toBe(true);
	});

	it('direct path order: once-removed first then short path — all edges present', () => {
		const dag = node({
			5: node({ 9: node({ 100: leaf }) }),
			20: node({ 100: leaf })
		});
		const seen = computeSeen(dag);

		expect(seen[9].children.has(100)).toBe(true);
		expect(seen[100].parents.has(9)).toBe(true);
		expect(seen[100].parents.has(20)).toBe(true);
		expect(seen[20].children.has(100)).toBe(true);
		expect(seen[5].children.has(9)).toBe(true);
	});

	it('two citing papers, one direct and one once-removed to same work', () => {
		const A = 1000;
		const I = 50;
		const C1 = 30;
		const C2 = 10;

		const dag = node({
			[C2]: node({ [A]: leaf }),
			[C1]: node({ [I]: node({ [A]: leaf }) })
		});
		const seen = computeSeen(dag);

		expect(seen[C2].children.has(A)).toBe(true);
		expect(seen[C1].children.has(I)).toBe(true);
		expect(seen[I].children.has(A)).toBe(true);
		expect(seen[A].parents.has(C2)).toBe(true);
		expect(seen[A].parents.has(I)).toBe(true);
	});

	it('shared intermediate reached by two citing papers', () => {
		const dag = node({
			1: node({ 5: node({ 100: leaf }) }),
			2: node({ 5: node({ 100: leaf }) })
		});
		const seen = computeSeen(dag);

		expect(seen[1].children.has(5)).toBe(true);
		expect(seen[2].children.has(5)).toBe(true);
		expect(seen[5].children.has(100)).toBe(true);
		expect(seen[5].parents.has(1)).toBe(true);
		expect(seen[5].parents.has(2)).toBe(true);
	});

	it('node promoted to shallower level keeps all previously found children', () => {
		const A = 99;
		const dag = node({
			1: node({ 2: node({ [A]: leaf }) }),
			3: node({ [A]: leaf })
		});
		const seen = computeSeen(dag);

		expect(seen[2].children.has(A)).toBe(true);
		expect(seen[3].children.has(A)).toBe(true);
		expect(seen[A].level).toBe(1);
	});
});

describe('buildSubgraphs', () => {
	it('pairs top-level papers by year descending', () => {
		// 4 citing papers → 2 subgraphs of 2 each
		const dag = node({
			1: node({ 10: leaf }),
			2: node({ 20: leaf }),
			3: node({ 30: leaf }),
			4: node({ 40: leaf })
		});
		const seen = computeSeen(dag);
		const papers = pm([1, 2020], [2, 2021], [3, 2022], [4, 2023]);
		const subs = buildSubgraphs(seen, papers);

		expect(subs.length).toBe(2);
		// Most recent first: 4, 3 in first group; 2, 1 in second group
		expect(subs[0]).toContain(4);
		expect(subs[0]).toContain(3);
		expect(subs[1]).toContain(2);
		expect(subs[1]).toContain(1);
	});

	it('follows children directionally and includes them', () => {
		// C1 → I → A, C2 → A
		const dag = node({
			1: node({ 5: node({ 100: leaf }) }),
			2: node({ 100: leaf })
		});
		const seen = computeSeen(dag);
		const papers = pm([1, 2023], [2, 2023], [5, 2020], [100, 2018]);
		const subs = buildSubgraphs(seen, papers);

		// All grouped together (only 2 top-level papers, group size 2)
		expect(subs.length).toBe(1);
		expect(subs[0]).toContain(1);
		expect(subs[0]).toContain(2);
		expect(subs[0]).toContain(5);
		expect(subs[0]).toContain(100);
	});

	it('does not let other top-level papers bleed into a subgraph', () => {
		// C1 → A, C2 → A, C3 → B - with group size 1
		const dag = node({
			1: node({ 100: leaf }),
			2: node({ 100: leaf }),
			3: node({ 200: leaf })
		});
		const seen = computeSeen(dag);
		const papers = pm([1, 2023], [2, 2022], [3, 2021], [100, 2015], [200, 2016]);
		const subs = buildSubgraphs(seen, papers, 1);

		expect(subs.length).toBe(3);
		// First subgraph starts from 1 (most recent)
		expect(subs[0]).toContain(1);
		expect(subs[0]).toContain(100);
		expect(subs[0]).not.toContain(2); // 2 is a top-level, shouldn't bleed in
	});

	it('single paper produces single subgraph', () => {
		const dag = node({ 1: node({ 100: leaf }) });
		const seen = computeSeen(dag);
		const papers = pm([1, 2023], [100, 2020]);
		const subs = buildSubgraphs(seen, papers);
		expect(subs.length).toBe(1);
		expect(subs[0].sort()).toEqual([1, 100]);
	});
});

describe('classifyComponentLayers', () => {
	it('classifies top, mid, bottom correctly', () => {
		const dag = node({ 1: node({ 2: node({ 3: leaf }) }) });
		const seen = computeSeen(dag);
		const authored = new Set([3]);
		const layers = classifyComponentLayers([1, 2, 3], seen, (w) => authored.has(w));

		expect(layers.top).toEqual([1]);
		expect(layers.mid).toEqual([2]);
		expect(layers.bottom).toEqual([3]);
	});

	it('all root children go to top when not authored', () => {
		const dag = node({ 1: leaf, 2: leaf });
		const seen = computeSeen(dag);
		const layers = classifyComponentLayers([1, 2], seen, () => false);

		expect(layers.top.sort()).toEqual([1, 2]);
		expect(layers.mid).toEqual([]);
		expect(layers.bottom).toEqual([]);
	});
});
