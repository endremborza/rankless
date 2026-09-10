import { describe, expect, it } from 'vitest';

import { latLonToMap } from './geo';

describe('map projection', () => {
	it('places known cities on the map plane', () => {
		const budapest = latLonToMap({ lat: 47.5, lon: 19.05 });
		const rio = latLonToMap({ lat: -22.9, lon: -43.2 });
		expect(budapest.x).toBeGreaterThan(1000);
		expect(budapest.y).toBeLessThan(rio.y);
		expect(rio.x).toBeLessThan(1000);
	});
});
