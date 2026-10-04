import { describe, it, expect } from 'vitest';
import { compactCount, niceTicks } from './year-ticks';

describe('niceTicks', () => {
	it('gives round values strictly inside (0, max)', () => {
		expect(niceTicks(1811)).toEqual([500, 1000, 1500]);
		expect(niceTicks(4)).toEqual([2]);
		expect(niceTicks(2.2e6)).toEqual([1000000, 2000000]);
		expect(niceTicks(0)).toEqual([]);
	});
});

describe('compactCount', () => {
	it('keeps three significant digits across unit boundaries', () => {
		expect(compactCount(495)).toBe('495');
		expect(compactCount(1000)).toBe('1k');
		expect(compactCount(999.7)).toBe('1k');
		expect(compactCount(1431)).toBe('1.43k');
		expect(compactCount(1500)).toBe('1.5k');
		expect(compactCount(1.994e6)).toBe('1.99M');
		expect(compactCount(30000)).toBe('30k');
		expect(compactCount(377600)).toBe('378k');
		expect(compactCount(1e6)).toBe('1M');
		expect(compactCount(2.5e9)).toBe('2.5B');
		expect(compactCount(0)).toBe('0');
	});
});
