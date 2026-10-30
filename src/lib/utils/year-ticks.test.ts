import { describe, it, expect } from 'vitest';
import { countGrid, niceTicks } from './year-ticks';

describe('niceTicks', () => {
	it('gives round values strictly inside (0, max)', () => {
		expect(niceTicks(1811)).toEqual([500, 1000, 1500]);
		expect(niceTicks(4)).toEqual([2]);
		expect(niceTicks(2.2e6)).toEqual([1000000, 2000000]);
		expect(niceTicks(0)).toEqual([]);
	});
});

describe('countGrid', () => {
	it('labels the whole-count gridlines with their unit', () => {
		expect(countGrid(2.2e6, 200, 15)).toEqual([
			{ v: 1e6, label: '1M' },
			{ v: 2e6, label: '2M' }
		]);
		expect(countGrid(1.5, 200, 15)).toEqual([{ v: 1, label: '1' }]);
	});
});
