import projection from '$lib/assets/data/map-projection.json';

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

export function utcDayStamp(date: Date = new Date()): string {
	return date.toISOString().slice(0, 10);
}

// Daily-streak rule: giving up breaks the streak; a finished guess extends a
// streak whose last play was yesterday and otherwise starts a fresh one.
export function nextStreak(prev: number, lastDay: string, day: string, gaveUp: boolean): number {
	if (gaveUp) return 0;
	const yesterday = utcDayStamp(new Date(Date.parse(day) - 24 * 60 * 60 * 1000));
	return lastDay === yesterday ? prev + 1 : 1;
}

export function dailyIndex(day: string, cardCount: number): number {
	let h = 0x811c9dc5;
	for (let i = 0; i < day.length; i++) {
		h ^= day.charCodeAt(i);
		h = Math.imul(h, 0x01000193);
	}
	return (h >>> 0) % cardCount;
}

export function ccFlag(cc: string): string {
	return [...cc.toUpperCase()]
		.map((c) => String.fromCodePoint(0x1f1e6 + c.charCodeAt(0) - 65))
		.join('');
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
	return `Rankless quiz ${day}\n${ladder} ${cluesUsed} clue${cluesUsed === 1 ? '' : 's'}, ${result}\nhttps://rankless.org/game`;
}
