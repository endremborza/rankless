import { describe, expect, it } from 'vitest';

import countryPaths from '$lib/assets/data/country-svg-paths.json';
import { latLonToMap } from './geo';

// Absolute-coordinate polygons of one country path list (M/L/z, with the
// relative forms the asset also uses).
function polygons(paths: string[]): [number, number][][] {
	const polys: [number, number][][] = [];
	for (const d of paths) {
		let cur: [number, number][] = [];
		let x = 0;
		let y = 0;
		let sx = 0;
		let sy = 0;
		let cmd = '';
		let nums: number[] = [];
		for (const m of d.matchAll(/([MmLlzZ])|(-?(?:\d+\.?\d*|\.\d+))/g)) {
			if (m[1]) {
				if (m[1] === 'z' || m[1] === 'Z') {
					if (cur.length) polys.push(cur);
					cur = [];
					x = sx;
					y = sy;
				} else cmd = m[1];
				nums = [];
				continue;
			}
			nums.push(Number(m[2]));
			if (nums.length < 2) continue;
			const [dx, dy] = nums;
			nums = [];
			if (cmd === 'M' || cmd === 'm') {
				[x, y] = cmd === 'M' ? [dx, dy] : [x + dx, y + dy];
				[sx, sy] = [x, y];
				if (cur.length) polys.push(cur);
				cur = [[x, y]];
				cmd = cmd === 'M' ? 'L' : 'l';
			} else {
				[x, y] = cmd === 'L' ? [dx, dy] : [x + dx, y + dy];
				cur.push([x, y]);
			}
		}
		if (cur.length) polys.push(cur);
	}
	return polys.filter((p) => p.length > 2);
}

function inside([px, py]: [number, number], poly: [number, number][]): boolean {
	let ins = false;
	for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
		const [x0, y0] = poly[i];
		const [x1, y1] = poly[j];
		if (y0 > py !== y1 > py && px < ((x1 - x0) * (py - y0)) / (y1 - y0) + x0) ins = !ins;
	}
	return ins;
}

const paths = countryPaths as Record<string, string[]>;

describe('map projection', () => {
	it('places known cities on the map plane', () => {
		const budapest = latLonToMap({ lat: 47.5, lon: 19.05 });
		const rio = latLonToMap({ lat: -22.9, lon: -43.2 });
		expect(budapest.x).toBeGreaterThan(1000);
		expect(budapest.y).toBeLessThan(rio.y);
		expect(rio.x).toBeLessThan(1000);
	});

	it('lands coastal campuses on their own country', () => {
		const coast: [string, number, number][] = [
			['United States', 47.61, -122.33], // Seattle
			['United States', 37.77, -122.42], // San Francisco
			['United States', 25.76, -80.19], // Miami
			['Canada', 49.28, -123.12], // Vancouver
			['Japan', 35.68, 139.69], // Tokyo
			['Australia', -31.95, 115.86], // Perth
			['South Africa', -33.93, 18.42], // Cape Town
			['Iceland', 64.15, -21.94], // Reykjavik
			['New Zealand', -36.85, 174.76] // Auckland
		];
		for (const [country, lat, lon] of coast) {
			const { x, y } = latLonToMap({ lat, lon });
			expect(
				polygons(paths[country]).some((poly) => inside([x, y], poly)),
				country
			).toBe(true);
		}
	});
});
