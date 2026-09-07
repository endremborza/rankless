import { describe, it, expect } from 'vitest';
import { createStaleGuard } from './stale-guard';

describe('createStaleGuard', () => {
	it('only the latest claim stays current', () => {
		const claim = createStaleGuard();
		const first = claim();
		expect(first()).toBe(true);
		const second = claim();
		expect(first()).toBe(false);
		expect(second()).toBe(true);
		claim();
		expect(second()).toBe(false);
	});
});
