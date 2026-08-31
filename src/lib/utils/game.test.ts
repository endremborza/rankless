import { describe, expect, it } from 'vitest';

import { ccFlag, ccName, dailyIndex, nextStreak, shareMessage, shuffle } from './game';

describe('nextStreak', () => {
	it('continues a streak from yesterday and starts one otherwise', () => {
		expect(nextStreak(3, '2026-08-22', '2026-08-23', false)).toBe(4);
		expect(nextStreak(3, '2026-08-20', '2026-08-23', false)).toBe(1);
		expect(nextStreak(0, '', '2026-08-23', false)).toBe(1);
	});

	it('breaks the streak on giving up', () => {
		expect(nextStreak(3, '2026-08-22', '2026-08-23', true)).toBe(0);
		expect(nextStreak(0, '', '2026-08-23', true)).toBe(0);
	});

	it('crosses month boundaries', () => {
		expect(nextStreak(9, '2026-08-31', '2026-09-01', false)).toBe(10);
	});
});

describe('dailyIndex', () => {
	it('is deterministic and in range', () => {
		const i = dailyIndex('2026-08-21', 24);
		expect(i).toBe(dailyIndex('2026-08-21', 24));
		expect(i).toBeGreaterThanOrEqual(0);
		expect(i).toBeLessThan(24);
	});

	it('varies across days', () => {
		const days = ['2026-08-21', '2026-08-22', '2026-08-23', '2026-08-24'];
		const inds = new Set(days.map((d) => dailyIndex(d, 24)));
		expect(inds.size).toBeGreaterThan(1);
	});
});

describe('shuffle', () => {
	const items = Array.from({ length: 20 }, (_, i) => i);

	it('is a permutation and does not mutate its input', () => {
		const a = shuffle(items);
		expect([...a].sort((x, y) => x - y)).toEqual(items);
		expect(items).toEqual(Array.from({ length: 20 }, (_, i) => i));
	});
});

describe('country display', () => {
	it('builds flags and English names from ISO codes', () => {
		expect(ccFlag('hu')).toBe('🇭🇺');
		expect(ccName('HU')).toBe('Hungary');
		expect(ccName('de')).toBe('Germany');
	});
});

describe('shareMessage', () => {
	it('stamps the day, line, and route URL', () => {
		expect(shareMessage('Rankless quiz', '2026-08-23', 'line here', '/game-clues')).toBe(
			'Rankless quiz 2026-08-23\nline here\nhttps://rankless.org/game-clues'
		);
	});
});
