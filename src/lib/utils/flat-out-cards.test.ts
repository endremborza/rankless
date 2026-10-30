import { describe, expect, it } from 'vitest';
import countryPaths from '$lib/assets/data/country-svg-paths.json';
import { mapCardLayout, placeLabels, type LabelAsk } from './flat-out-cards';
import { overlaps, type Box } from './label-placement';
import { countryLevels, countryStyles, subfieldStyles } from './flat-out-styles';

const BOUNDS = { x: 0, y: 0, w: 400, h: 200 };

function ask(x: number, y: number, w = 80): LabelAsk {
	return { anchor: { x, y }, w, h: 20, gap: 6, centred: false };
}

function disjoint(a: Box, b: Box): boolean {
	return !overlaps(a, b);
}

describe('subfieldStyles', () => {
	it('sizes a lone field like the heaviest of several', () => {
		const lone = subfieldStyles({ 5: { w: 3, id: 5 } }, false)[5];
		const heaviest = subfieldStyles({ 5: { w: 3, id: 5 }, 6: { w: 1, id: 6 } }, false)[5];
		expect(lone.r).toBe(heaviest.r);
	});
});

describe('countryLevels', () => {
	// Node ids, names and OpenAlex ids as the backend serves them.
	const countries = {
		80: { name: 'Türkiye', oaId: 21076, specBaseline: 1 },
		47: { name: 'Bosnia and Herzegovina', oaId: 16706, specBaseline: 1 },
		162: { name: 'Democratic Republic of the Congo', oaId: 17475, specBaseline: 1 }
	};
	const flatOut = { 80: { w: 9, id: 80 }, 47: { w: 5, id: 47 }, 162: { w: 2, id: 162 } };

	it('keys every country by a path the map draws, whatever its name', () => {
		const levels = countryLevels(flatOut, { countries });
		expect(Object.values(levels).map((l) => l.id)).toHaveLength(Object.keys(countries).length);
		expect(Object.keys(countryPaths)).toEqual(expect.arrayContaining(Object.keys(levels)));
	});
});

describe('placeLabels', () => {
	const tight = { x: 0, y: 0, w: 120, h: 24 };

	it('drops a label with no free spot and keeps the earlier one', () => {
		const [first, second] = placeLabels([ask(100, 12), ask(104, 12)], 0, tight, [], []);
		expect(first).not.toBeNull();
		expect(second).toBeNull();
	});

	it('draws a must label even where every spot collides', () => {
		const placed = placeLabels([ask(100, 12), ask(104, 12)], 2, tight, [], []);
		expect(placed.every((p) => p != null)).toBe(true);
	});

	it('moves a label off a neighbour instead of dropping it', () => {
		const placed = placeLabels([ask(100, 100), ask(110, 110)], 0, BOUNDS, [], []);
		expect(placed.every((p) => p != null)).toBe(true);
		expect(disjoint(placed[0]!, placed[1]!)).toBe(true);
	});

	it('keeps a label off obstacles', () => {
		const obstacle = { x: 106, y: 90, w: 100, h: 20 };
		const [p] = placeLabels([ask(100, 100)], 0, BOUNDS, [obstacle], []);
		expect(p).not.toBeNull();
		expect(disjoint(p!, obstacle)).toBe(true);
	});

	it("keeps a label off the other asks' marks but not off its own", () => {
		const own = { x: 96, y: 96, w: 8, h: 8 };
		const other = { x: 150, y: 96, w: 8, h: 8 };
		const [p] = placeLabels([ask(100, 100), ask(154, 100)], 0, BOUNDS, [], [own, other]);
		expect(p?.align).toBe('end');
		expect(disjoint(p!, other)).toBe(true);
	});
});

describe('mapCardLayout', () => {
	const names: Record<string, string> = {
		US: 'United States',
		CN: 'China',
		DE: 'Germany',
		GB: 'United Kingdom',
		FR: 'France',
		NL: 'Netherlands',
		BE: 'Belgium',
		CH: 'Switzerland',
		AT: 'Austria',
		HU: 'Hungary'
	};
	const levels = Object.fromEntries(
		Object.keys(names).map((code, i) => [code, { w: 1000 - i * 90, id: i }])
	);
	const styles = countryStyles(levels);

	it('never prints two labels over each other in a crowded Europe', () => {
		const { labels } = mapCardLayout(styles, ['HU', 'BE'], names, 'Citations');
		for (const [i, a] of labels.entries())
			for (const b of labels.slice(i + 1)) expect(disjoint(a, b)).toBe(true);
	});

	it('always names the highlighted countries, first', () => {
		const { labels } = mapCardLayout(styles, ['HU', 'BE'], names, 'Citations');
		expect(labels.slice(0, 2).map((l) => [l.name, l.hl])).toEqual([
			['Hungary', true],
			['Belgium', true]
		]);
	});
});
