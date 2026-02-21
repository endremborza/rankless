import { describe, it, expect } from 'vitest';
import { getColorArr, getColor } from './style-util';

describe('getColorArr', () => {
	it('returns 3-element array', () => {
		const arr = getColorArr(0.5);
		expect(arr).toHaveLength(3);
	});
	it('gives blue-ish at rate 0', () => {
		const [r, , b] = getColorArr(0);
		expect(r).toBe(0);
		expect(b).toBe(255);
	});
	it('gives red-ish at rate 1', () => {
		const [r, , b] = getColorArr(1);
		expect(r).toBe(250);
		expect(b).toBe(5);
	});
	it('mid rate has low deviation channel', () => {
		const [, g] = getColorArr(0.5);
		expect(g).toBeCloseTo(0, 0);
	});
});

describe('getColor', () => {
	it('returns rgb string', () => {
		const color = getColor(0.5);
		expect(color).toMatch(/^rgb\(\d+/);
	});
});
