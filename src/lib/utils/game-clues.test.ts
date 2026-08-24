import { describe, expect, it } from 'vitest';

import { haversineKm, latLonToMap, mapToLatLon, roundScore, shareText } from './game-clues';

describe('map projection', () => {
	it('round-trips lat/lon through map coordinates', () => {
		const p = { lat: 47.5, lon: 19.05 };
		const { x, y } = latLonToMap(p);
		const back = mapToLatLon(x, y);
		expect(back.lat).toBeCloseTo(p.lat, 6);
		expect(back.lon).toBeCloseTo(p.lon, 6);
	});

	it('places known cities on the map plane', () => {
		const budapest = latLonToMap({ lat: 47.5, lon: 19.05 });
		const rio = latLonToMap({ lat: -22.9, lon: -43.2 });
		expect(budapest.x).toBeGreaterThan(1000);
		expect(budapest.y).toBeLessThan(rio.y);
		expect(rio.x).toBeLessThan(1000);
	});
});

describe('haversineKm', () => {
	it('measures Budapest to Vienna at ~215 km', () => {
		const d = haversineKm({ lat: 47.4979, lon: 19.0402 }, { lat: 48.2082, lon: 16.3738 });
		expect(d).toBeGreaterThan(190);
		expect(d).toBeLessThan(240);
	});

	it('is zero for identical points', () => {
		expect(haversineKm({ lat: 1, lon: 2 }, { lat: 1, lon: 2 })).toBe(0);
	});
});

describe('roundScore', () => {
	it('rewards exact early guesses most', () => {
		expect(roundScore(0, 1)).toBe(1000);
		expect(roundScore(0, 6)).toBeLessThan(roundScore(0, 1));
		expect(roundScore(2000, 1)).toBeLessThan(roundScore(100, 1));
	});

	it('never goes negative', () => {
		expect(roundScore(20000, 6)).toBeGreaterThanOrEqual(0);
	});
});

describe('shareText', () => {
	it('pads the ladder to the clue count actually offered', () => {
		const text = shareText('2026-08-23', 2, 5, 120, 640);
		expect(text).toContain('🟩🟩⬜⬜⬜');
		expect(text).not.toContain('⬜⬜⬜⬜');
		expect(text).toContain('https://rankless.org/game-clues');
	});
});
