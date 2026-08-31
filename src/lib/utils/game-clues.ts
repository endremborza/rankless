// Math for the clue-ladder game (/game-clues): map↔lat/lon projection,
// haversine, distance×clue scoring, share text. Shared game plumbing is in
// utils/game.ts, types in types/game-clues.ts.

import projection from '$lib/assets/data/map-projection.json';
import { shareMessage } from '$lib/utils/game';

export type LatLon = { lat: number; lon: number };

export const N_CLUES = 6;

const EARTH_RADIUS_KM = 6371;
const DISTANCE_SCALE_KM = 1500;
const MAX_SCORE = 1000;

export function mapToLatLon(x: number, y: number): LatLon {
	return {
		lat: (y - projection.yOffset) / projection.yPerLat,
		lon: (x - projection.xOffset) / projection.xPerLon
	};
}

export function latLonToMap(p: LatLon): { x: number; y: number } {
	return {
		x: projection.xOffset + projection.xPerLon * p.lon,
		y: projection.yOffset + projection.yPerLat * p.lat
	};
}

export function haversineKm(a: LatLon, b: LatLon): number {
	const rad = (d: number) => (d * Math.PI) / 180;
	const dLat = rad(b.lat - a.lat);
	const dLon = rad(b.lon - a.lon);
	const h =
		Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2;
	return 2 * EARTH_RADIUS_KM * Math.asin(Math.sqrt(h));
}

export function roundScore(distanceKm: number, cluesUsed: number): number {
	const clueFactor = (N_CLUES + 1 - cluesUsed) / N_CLUES;
	return Math.round(MAX_SCORE * Math.exp(-distanceKm / DISTANCE_SCALE_KM) * clueFactor);
}

export function shareText(
	day: string,
	cluesUsed: number,
	totalClues: number,
	distanceKm: number | null,
	score: number
): string {
	const ladder = '🟩'.repeat(cluesUsed) + '⬜'.repeat(Math.max(0, totalClues - cluesUsed));
	const result = distanceKm == null ? 'gave up' : `${Math.round(distanceKm)} km off → ${score} pts`;
	return shareMessage(
		'Rankless quiz',
		day,
		`${ladder} ${cluesUsed} clue${cluesUsed === 1 ? '' : 's'}, ${result}`,
		'/game-clues'
	);
}
