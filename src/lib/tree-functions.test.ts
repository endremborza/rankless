import { describe, it, expect, vi } from 'vitest';

vi.mock('$app/paths', () => ({ base: '' }));
vi.mock('$lib/constants', () => ({
	COMPLETE_YEAR: 1950,
	DEFAULT_LIMIT_N: 10,
	MAX_LEVEL_COUNT: 4,
	ENTITY_TYPES: ['topics', 'works', 'qs', 'authors', 'institutions', 'sources', 'countries', 'subfields', 'hit-papers']
}));

import {
	insertKeepingOrder,
	getNodeByPath,
	isPathInTree,
	pruneTree,
	intersectionTree,
	getFlatRescaler,
	getDefaultControlSpecs,
	getDefaultLevelSpecs,
	idFromBd,
	urlFriendlify,
	getDefaultYear,
	deriveVisibleTree,
	nameById,
	UNKNOWN_NAME
} from './tree-functions';
import type * as tt from './tree-types';

describe('insertKeepingOrder', () => {
	const numCmp = (a: number, b: number) => a - b;

	it('inserts into empty array', () => {
		const arr: number[] = [];
		insertKeepingOrder(5, arr, numCmp);
		expect(arr).toEqual([5]);
	});

	it('maintains sorted order', () => {
		const arr = [1, 3, 5, 7];
		insertKeepingOrder(4, arr, numCmp);
		expect(arr).toEqual([1, 3, 4, 5, 7]);
	});

	it('inserts at beginning', () => {
		const arr = [2, 4, 6];
		insertKeepingOrder(1, arr, numCmp);
		expect(arr).toEqual([1, 2, 4, 6]);
	});

	it('inserts at end', () => {
		const arr = [1, 3, 5];
		insertKeepingOrder(7, arr, numCmp);
		expect(arr).toEqual([1, 3, 5, 7]);
	});

	it('handles duplicates', () => {
		const arr = [1, 3, 5];
		insertKeepingOrder(3, arr, numCmp);
		expect(arr).toEqual([1, 3, 3, 5]);
	});
});

describe('getNodeByPath', () => {
	const tree: tt.ResponseNode = {
		linkCount: 100, sourceCount: 0, topSourceId: 0, topSourceLinks: 0,
		children: {
			1: {
				linkCount: 50, sourceCount: 0, topSourceId: 0, topSourceLinks: 0,
				children: {
					10: { linkCount: 25, sourceCount: 0, topSourceId: 0, topSourceLinks: 0 }
				}
			},
			2: { linkCount: 30, sourceCount: 0, topSourceId: 0, topSourceLinks: 0 }
		}
	};

	it('returns root for empty path', () => {
		expect(getNodeByPath([], tree)).toBe(tree);
	});

	it('finds depth-1 node', () => {
		const node = getNodeByPath([1], tree);
		expect(node?.linkCount).toBe(50);
	});

	it('finds depth-2 node', () => {
		const node = getNodeByPath([1, 10], tree);
		expect(node?.linkCount).toBe(25);
	});

	it('returns undefined for missing path', () => {
		expect(getNodeByPath([99], tree)).toBeUndefined();
	});

	it('returns undefined for undefined root', () => {
		expect(getNodeByPath([1], undefined)).toBeUndefined();
	});
});

describe('isPathInTree', () => {
	const tree: tt.BareNode = {
		children: { 1: { children: { 10: { children: {} } } }, 2: { children: {} } }
	};

	it('returns true for existing path', () => {
		expect(isPathInTree([1], tree)).toBe(true);
		expect(isPathInTree([1, 10], tree)).toBe(true);
	});

	it('returns false for missing path', () => {
		expect(isPathInTree([99], tree)).toBe(false);
		expect(isPathInTree([1, 99], tree)).toBe(false);
	});

	it('returns true for empty path (root)', () => {
		expect(isPathInTree([], tree)).toBe(true);
	});
});

describe('pruneTree', () => {
	const tree: tt.BareNode = {
		children: { 1: { children: { 10: { children: { 100: { children: {} } } } } } }
	};

	it('depth 0 returns empty children', () => {
		expect(pruneTree(tree, 0)).toEqual({ children: {} });
	});

	it('depth 1 keeps first level only', () => {
		const pruned = pruneTree(tree, 1);
		expect(pruned.children).toHaveProperty('1');
		expect((pruned.children as any)[1].children).toEqual({});
	});

	it('depth 2 keeps two levels', () => {
		const pruned = pruneTree(tree, 2);
		expect((pruned.children as any)[1].children).toHaveProperty('10');
		expect((pruned.children as any)[1].children[10].children).toEqual({});
	});
});

describe('intersectionTree', () => {
	it('returns shared keys only', () => {
		const a: tt.BareNode = { children: { 1: { children: {} }, 2: { children: {} } } };
		const b: tt.BareNode = { children: { 2: { children: {} }, 3: { children: {} } } };
		const result = intersectionTree(a, b);
		expect(Object.keys(result.children || {})).toEqual(['2']);
	});

	it('returns empty for no overlap', () => {
		const a: tt.BareNode = { children: { 1: { children: {} } } };
		const b: tt.BareNode = { children: { 2: { children: {} } } };
		expect(Object.keys(intersectionTree(a, b).children || {})).toEqual([]);
	});

	it('handles undefined children', () => {
		const a: tt.BareNode = { children: undefined as any };
		const b: tt.BareNode = { children: { 1: { children: {} } } };
		expect(Object.keys(intersectionTree(a, b).children || {})).toEqual([]);
	});
});

describe('getFlatRescaler', () => {
	it('computes min/max and scaler', () => {
		const levels: tt.LevelT = {
			a: { w: 10, id: 1 },
			b: { w: 50, id: 2 },
			c: { w: 30, id: 3 }
		};
		const result = getFlatRescaler(levels, 0, 0);
		expect(result.locMinw).toBe(10);
		expect(result.locMaxw).toBe(50);
		expect(result.linScaler(10)).toBeCloseTo(0);
		expect(result.linScaler(50)).toBeCloseTo(1);
		expect(result.linScaler(30)).toBeCloseTo(0.5);
	});

	it('handles single value', () => {
		const levels: tt.LevelT = { a: { w: 5, id: 1 } };
		const result = getFlatRescaler(levels, 0, 0);
		expect(result.locMinw).toBe(5);
		expect(result.locMaxw).toBe(5);
	});
});

describe('getDefaultControlSpecs', () => {
	it('returns specialization sizeBase when spec=true', () => {
		const specs = getDefaultControlSpecs(true);
		expect(specs.globalSizeBase).toBe('specialization');
	});

	it('returns volume sizeBase when spec=false', () => {
		const specs = getDefaultControlSpecs(false);
		expect(specs.globalSizeBase).toBe('volume');
	});

	it('creates correct number of level specs', () => {
		const specs = getDefaultControlSpecs(true);
		expect(specs.levelSpecs).toHaveLength(4);
	});

	it('level specs are independent objects', () => {
		const specs = getDefaultControlSpecs(true);
		specs.levelSpecs[0].include.push(1);
		expect(specs.levelSpecs[1].include).toEqual([]);
	});
});

describe('getDefaultLevelSpecs', () => {
	it('returns 4 level specs', () => {
		expect(getDefaultLevelSpecs()).toHaveLength(4);
	});
	it('all invisible by default', () => {
		expect(getDefaultLevelSpecs().every(l => !l.isVisible)).toBe(true);
	});
});

describe('idFromBd', () => {
	it('formats breakdown id', () => {
		expect(idFromBd({ attributeType: 'authors', specDenomInd: 0, sourceSide: true }))
			.toBe('authors-true');
		expect(idFromBd({ attributeType: 'countries', specDenomInd: 1, sourceSide: false }))
			.toBe('countries-false');
	});
});

describe('urlFriendlify', () => {
	it('escapes slashes', () => {
		expect(urlFriendlify('a/b')).toBe('a%2Fb');
	});
	it('no-op for safe strings', () => {
		expect(urlFriendlify('hello')).toBe('hello');
	});
});

describe('getDefaultYear', () => {
	it('returns COMPLETE_YEAR for authors', () => {
		expect(getDefaultYear('authors')).toBe(1950);
	});
	it('returns 2020 for countries', () => {
		expect(getDefaultYear('countries')).toBe(2020);
	});
	it('returns 2020 for subfields', () => {
		expect(getDefaultYear('subfields')).toBe(2020);
	});
});

describe('nameById', () => {
	it('returns name from labels', () => {
		const labels = { authors: { '5': { name: 'Alice', specBaseline: 0 } } } as any;
		expect(nameById(labels, 'authors', 5)).toBe('Alice');
	});

	it('returns UNKNOWN_NAME for missing id', () => {
		const labels = { authors: {} } as any;
		expect(nameById(labels, 'authors', 99)).toBe(UNKNOWN_NAME);
	});

	it('returns UNKNOWN_NAME for missing entity type', () => {
		expect(nameById({} as any, 'authors', 1)).toBe(UNKNOWN_NAME);
	});
});

describe('deriveVisibleTree', () => {
	it('produces valid tree info for simple input', () => {
		const root: tt.ResponseNode = {
			linkCount: 100, sourceCount: 10, topSourceId: 1, topSourceLinks: 5,
			children: {
				1: { linkCount: 60, sourceCount: 5, topSourceId: 1, topSourceLinks: 3 },
				2: { linkCount: 40, sourceCount: 5, topSourceId: 2, topSourceLinks: 2 }
			}
		};
		const treeSpec: tt.TreeSpec = {
			rootType: 'authors',
			breakdowns: [{ attributeType: 'subfields', specDenomInd: 0, sourceSide: true }],
			defaultIsSpec: false
		};
		const controls: tt.FullControlSpecs = {
			globalLimit: 10,
			globalSizeBase: 'volume',
			levelSpecs: [{ include: [], exclude: [], limit: 10, showTop: true, sizeBase: 'volume' }]
		};
		const labels = { subfields: { '1': { name: 'A', specBaseline: 0.5 }, '2': { name: 'B', specBaseline: 0.5 } } } as any;

		const result = deriveVisibleTree(root, controls, {}, labels, treeSpec);
		expect(result.tree.weight).toBe(100);
		expect(result.meta).toHaveLength(2);
		expect(result.meta[0].totalWeight).toBe(100);
		const childKeys = Object.keys(result.tree.children || {});
		expect(childKeys.length).toBe(2);
	});
});

describe('network-util pure functions', async () => {
	const { getIndex, circleLayout } = await import('./network-util');

	it('getIndex returns correct triangle index', () => {
		expect(getIndex(0, 1, 4)).toBe(0);
		expect(getIndex(0, 2, 4)).toBe(1);
		expect(getIndex(0, 3, 4)).toBe(2);
		expect(getIndex(1, 2, 4)).toBe(3);
		expect(getIndex(0, 0, 4)).toBe(-1);
	});

	it('getIndex is symmetric', () => {
		expect(getIndex(2, 0, 5)).toBe(getIndex(0, 2, 5));
	});

	it('circleLayout returns positions for all nodes', () => {
		const positions = circleLayout(['a', 'b', 'c'], [], { width: 100, height: 100 });
		expect(positions).toHaveLength(3);
		for (const p of positions) {
			expect(p.x).toBeGreaterThanOrEqual(0);
			expect(p.y).toBeGreaterThanOrEqual(0);
		}
	});
});
