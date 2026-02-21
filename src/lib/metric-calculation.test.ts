import { describe, it, expect } from 'vitest';
import { getSpecMetricObject } from './metric-calculation';
import type { ResponseNode } from './tree-types';

function makeNode(linkCount: number): ResponseNode {
	return { linkCount, sourceCount: 0, topSourceId: 0, topSourceLinks: 0 };
}

describe('getSpecMetricObject', () => {
	it('computes spec metric with baseline from labels', () => {
		const node = makeNode(100);
		const labels = { '5': { name: 'test', specBaseline: 0.1 } };
		const result = getSpecMetricObject(node, 1000, labels, 5);
		expect(result.nodeRate).toBe(0.1);
		expect(result.baselineRate).toBe(0.1);
		expect(result.specMetric).toBe(1.0);
	});

	it('uses fallback baseline when labels undefined', () => {
		const node = makeNode(200);
		const result = getSpecMetricObject(node, 1000, undefined, 5);
		expect(result.nodeRate).toBe(0.2);
		expect(result.baselineRate).toBe(0.1);
		expect(result.specMetric).toBe(2.0);
	});

	it('uses fallback baseline when childId not in labels', () => {
		const node = makeNode(200);
		const labels = { '99': { name: 'other', specBaseline: 0.5 } };
		const result = getSpecMetricObject(node, 1000, labels, 5);
		expect(result.baselineRate).toBe(0.1);
	});

	it('handles zero linkCount', () => {
		const node = makeNode(0);
		const labels = { '1': { name: 'x', specBaseline: 0.5 } };
		const result = getSpecMetricObject(node, 1000, labels, 1);
		expect(result.nodeRate).toBe(0);
		expect(result.specMetric).toBe(0);
	});
});
