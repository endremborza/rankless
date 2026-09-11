// The world-map asset's projection: Robinson, with the scale and offsets fit
// by pyscripts/calibrate_map.py into map-projection.json. Robinson's parallel
// lengths and spacings are tabulated per 5° of latitude and interpolated.

import projection from '$lib/assets/data/map-projection.json';

export type LatLon = { lat: number; lon: number };

const STEP = 5;
const PARALLEL_LENGTH = [
	1, 0.9986, 0.9954, 0.99, 0.9822, 0.973, 0.96, 0.9427, 0.9216, 0.8962, 0.8679, 0.835, 0.7986,
	0.7597, 0.7186, 0.6732, 0.6213, 0.5722, 0.5322
];
const PARALLEL_DISTANCE = [
	0, 0.062, 0.124, 0.186, 0.248, 0.31, 0.372, 0.434, 0.4958, 0.5571, 0.6176, 0.6769, 0.7346, 0.7903,
	0.8435, 0.8936, 0.9394, 0.9761, 1
];

function tabulated(table: number[], lat: number): number {
	const t = Math.min(Math.abs(lat), 90) / STEP;
	const i = Math.min(Math.floor(t), table.length - 2);
	return table[i] + (table[i + 1] - table[i]) * (t - i);
}

export function latLonToMap(p: LatLon): { x: number; y: number } {
	const distance = Math.sign(p.lat) * tabulated(PARALLEL_DISTANCE, p.lat);
	return {
		x: projection.xOffset + projection.xScale * tabulated(PARALLEL_LENGTH, p.lat) * p.lon,
		y: projection.yOffset + projection.yScale * distance
	};
}
