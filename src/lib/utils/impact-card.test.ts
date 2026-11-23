import { describe, expect, it } from 'vitest';
import { fitBadges, uncross } from './impact-card';

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

describe('fitBadges', () => {
	const badge = (label: string) => ({ label, fill: '', ink: '' });

	it('keeps the leading badges that fit', () => {
		const badges = [badge('Hit'), badge('Nobel laureate'), badge('Leading researcher')];
		expect(fitBadges(badges, 160).map((b) => b.label)).toEqual(['Hit', 'Nobel laureate']);
	});

	it('clips a first badge too wide on its own', () => {
		const [only] = fitBadges([badge('Proceedings of the National Academy of Sciences')], 160);
		expect(only.label.endsWith('…')).toBe(true);
	});
});
