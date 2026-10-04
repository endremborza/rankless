import { describe, expect, it } from 'vitest';
import { uncross } from './impact-card';

describe('uncross', () => {
	it('keeps the given order when nothing crosses', () => {
		expect(
			uncross(2, 2, [
				[0, 0],
				[1, 1]
			])
		).toEqual({ top: [0, 1], bottom: [0, 1] });
	});

	it('reorders the rows to remove crossings', () => {
		const { top, bottom } = uncross(3, 3, [
			[0, 2],
			[1, 1],
			[2, 0],
			[0, 1]
		]);
		const at = (t: number, b: number): [number, number] => [top.indexOf(t), bottom.indexOf(b)];
		const edges = [at(0, 2), at(1, 1), at(2, 0), at(0, 1)];
		const crossing = edges.some(([t1, b1]) => edges.some(([t2, b2]) => (t1 - t2) * (b1 - b2) < 0));
		expect(crossing).toBe(false);
	});
});
