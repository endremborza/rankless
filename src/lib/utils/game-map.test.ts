import { describe, expect, it } from 'vitest';
import { latLonToMap } from './geo';
import { FONT, RADIUS, extent, frame, placeLabels, type Mark } from './game-map';

// Today's Caltech card: two campuses in the Los Angeles basin, three on one
// coordinate cluster in San Diego, every name longer than half the frame.
const CARD: [string, number, number, boolean][] = [
	['California Institute of Technology', 34.1377, -118.1253, false],
	['University of California, Los Angeles', 34.0689, -118.4452, true],
	['University of California San Diego', 32.8801, -117.234, false],
	['Scripps Research Institute', 32.8687, -117.2415, false],
	['Salk Institute for Biological Studies', 32.8872, -117.2456, false]
];

function marks(): Mark[] {
	return CARD.map(([label, lat, lon, answer], i) => ({
		...latLonToMap({ lat, lon }),
		label,
		answer,
		anchor: i === 0
	}));
}

describe('placeLabels', () => {
	const ms = marks();
	const b = frame(ms);
	const fs = b.w * FONT;
	const placed = placeLabels(ms, b, fs, b.w * RADIUS);

	it('keeps every label inside the frame', () => {
		for (const p of placed) {
			const [l, r] = extent(p, fs);
			expect(l, p.label).toBeGreaterThanOrEqual(b.x);
			expect(r, p.label).toBeLessThanOrEqual(b.x + b.w);
			expect(p.ty, p.label).toBeGreaterThanOrEqual(b.y + fs * 0.9);
			expect(p.ty, p.label).toBeLessThanOrEqual(b.y + b.h);
		}
	});

	it('prints no two labels over each other', () => {
		for (const [i, p] of placed.entries()) {
			for (const q of placed.slice(0, i)) {
				const [pl, pr] = extent(p, fs);
				const [ql, qr] = extent(q, fs);
				const overlapX = pl < qr && ql < pr;
				expect(overlapX && Math.abs(p.ty - q.ty) < fs, `${p.label} / ${q.label}`).toBe(false);
			}
		}
	});
});
