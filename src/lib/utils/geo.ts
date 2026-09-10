// The world-map asset's projection (fit by pyscripts/calibrate_map.py into
// map-projection.json).

import projection from '$lib/assets/data/map-projection.json';

export type LatLon = { lat: number; lon: number };

export function latLonToMap(p: LatLon): { x: number; y: number } {
	return {
		x: projection.xOffset + projection.xPerLon * p.lon,
		y: projection.yOffset + projection.yPerLat * p.lat
	};
}
