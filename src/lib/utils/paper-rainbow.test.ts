import { describe, expect, it } from 'vitest';
import { LATEST_YEAR } from '$lib/constants';
import type * as tt from '$lib/tree-types';
import { getFigureBasis, xBase, yBase } from './paper-rainbow';

function paper(year: number, yearlyCites: number[]): tt.Paper {
	const citations = yearlyCites.reduce((a, b) => a + b, 0);
	return {
		wid: year,
		oaId: year,
		year,
		name: `<i>p</i>${year}`,
		doi: '',
		citations,
		source: 0,
		authorships: [],
		yearlyCites,
		isHit: true
	};
}

function points(path: string): [number, number][] {
	return [...path.matchAll(/[ML] (-?[\d.]+) (-?[\d.]+)/g)].map((m) => [Number(m[1]), Number(m[2])]);
}

describe('getFigureBasis', () => {
	const old = paper(LATEST_YEAR - 4, [10, 20, 30, 40, 50]);
	const recent = paper(LATEST_YEAR - 2, [5, 5, 5]);
	const ps = [old, recent];

	it('aligns trajectories at publication and scales the most cited to the full box', () => {
		const fb = getFigureBasis(ps, [0, 1], old.year, true, [0, 1], false);
		const [a, b] = fb.figPapers.map((p) => points(p.path));
		expect(a[0]).toEqual([0, -0.8]);
		expect(a.at(-1)).toEqual([xBase, -yBase]);
		expect(b[0][0]).toBe(0);
		expect(b.at(-1)).toEqual([xBase / 2, -1.2]);
		expect(fb.figPapers[0].endY).toBe(-yBase + 0.8);
		expect(fb.yTicks.map((t) => t.label)).toEqual(['50', '100', '150']);
		expect(fb.yearTicks.filter((t) => t.name !== undefined).map((t) => t.name)).toEqual([
			0,
			'+1',
			'+2'
		]);
	});

	it('starts each trajectory at its publication year when not aligned', () => {
		const fb = getFigureBasis(ps, [0, 1], old.year, false, [0, 1], false);
		expect(points(fb.figPapers[1].path)[0][0]).toBe(xBase / 2);
		expect(fb.pubMarks.map((m) => m.x)).toEqual([0, xBase / 2]);
	});
});
