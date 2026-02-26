import { describe, it, expect } from 'vitest';
import { computeSeen } from './dag-builder';
import type { RefTree } from '$lib/tree-types';

const leaf: RefTree = 'Leaf';
const node = (children: Record<number, RefTree>): RefTree => ({ Node: children });

describe('computeSeen', () => {
	it('single direct edge', () => {
		const dag = node({ 1: node({ 2: leaf }) });
		const seen = computeSeen(dag);
		expect(seen[1].children.has(2)).toBe(true);
		expect(seen[2].parents.has(1)).toBe(true);
	});

	it('direct path order: short path first then once-removed — edge not lost', () => {
		// C2 (key=2) < C1 (key=10) so C2 is processed first by numeric key order.
		// C2 → A (direct, depth 1), C1 → I → A (once-removed, A would be at depth 2).
		// Bug: when A already sat at depth 1, the I→A edge was silently dropped.
		const dag = node({
			2: node({ 100: leaf }), // C2 → A (direct)
			10: node({ 9: node({ 100: leaf }) }) // C1 → I → A (once-removed)
		});
		const seen = computeSeen(dag);

		expect(seen[9].children.has(100)).toBe(true); // I → A must be present
		expect(seen[100].parents.has(9)).toBe(true); // A's parent includes I
		expect(seen[100].parents.has(2)).toBe(true); // A's parent also includes C2
		expect(seen[2].children.has(100)).toBe(true); // C2 → A direct
		expect(seen[10].children.has(9)).toBe(true); // C1 → I
	});

	it('direct path order: once-removed first then short path — all edges present', () => {
		// C1 (key=5) < C2 (key=20) so once-removed path is processed first.
		const dag = node({
			5: node({ 9: node({ 100: leaf }) }), // C1 → I → A
			20: node({ 100: leaf }) // C2 → A (direct)
		});
		const seen = computeSeen(dag);

		expect(seen[9].children.has(100)).toBe(true);
		expect(seen[100].parents.has(9)).toBe(true);
		expect(seen[100].parents.has(20)).toBe(true);
		expect(seen[20].children.has(100)).toBe(true);
		expect(seen[5].children.has(9)).toBe(true);
	});

	it('two citing papers, one direct and one once-removed to same work — both I→A and C2→A edges present', () => {
		// Mimics the markus-j-buehler scenario: a citing hit paper (C2, small id)
		// directly cites the authored work A, while another citing paper (C1) goes
		// through an intermediate paper I before reaching A.
		const A = 1000;
		const I = 50;
		const C1 = 30;
		const C2 = 10; // smaller id ⟹ processed first

		const dag = node({
			[C2]: node({ [A]: leaf }),
			[C1]: node({ [I]: node({ [A]: leaf }) })
		});
		const seen = computeSeen(dag);

		// Direct edge
		expect(seen[C2].children.has(A)).toBe(true);
		// Once-removed edges
		expect(seen[C1].children.has(I)).toBe(true);
		expect(seen[I].children.has(A)).toBe(true); // was the lost edge
		// A knows about both parents
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
		// A is first found at depth 2 (via 1→2→A), then at depth 1 (via 3→A).
		// After promotion, 2's child link to A must survive.
		const A = 99;
		const dag = node({
			1: node({ 2: node({ [A]: leaf }) }),
			3: node({ [A]: leaf })
		});
		const seen = computeSeen(dag);

		expect(seen[2].children.has(A)).toBe(true); // promotion must not erase child
		expect(seen[3].children.has(A)).toBe(true);
		expect(seen[A].level).toBe(1); // promoted
	});
});
