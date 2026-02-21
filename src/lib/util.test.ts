import { describe, it, expect, vi } from 'vitest';
import { randN, debounce } from './util';

describe('randN', () => {
	it('returns integer in [0, n)', () => {
		for (let i = 0; i < 50; i++) {
			const r = randN(10);
			expect(r).toBeGreaterThanOrEqual(0);
			expect(r).toBeLessThan(10);
			expect(Number.isInteger(r)).toBe(true);
		}
	});
});

describe('debounce', () => {
	it('calls function after delay', () => {
		vi.useFakeTimers();
		const fn = vi.fn();
		const debounced = debounce(fn, 100);
		debounced();
		expect(fn).not.toHaveBeenCalled();
		vi.advanceTimersByTime(100);
		expect(fn).toHaveBeenCalledOnce();
		vi.useRealTimers();
	});

	it('resets timer on repeated calls', () => {
		vi.useFakeTimers();
		const fn = vi.fn();
		const debounced = debounce(fn, 100);
		debounced();
		vi.advanceTimersByTime(50);
		debounced();
		vi.advanceTimersByTime(50);
		expect(fn).not.toHaveBeenCalled();
		vi.advanceTimersByTime(50);
		expect(fn).toHaveBeenCalledOnce();
		vi.useRealTimers();
	});

	it('passes arguments through', () => {
		vi.useFakeTimers();
		const fn = vi.fn();
		const debounced = debounce(fn, 100);
		debounced('a', 'b');
		vi.advanceTimersByTime(100);
		expect(fn).toHaveBeenCalledWith('a', 'b');
		vi.useRealTimers();
	});
});
