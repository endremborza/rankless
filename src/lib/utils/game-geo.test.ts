import { describe, expect, it } from 'vitest';

import type { CardKind, PlayCard } from '../types/game-geo';
import {
	BRAND,
	DAILY_RECIPE,
	DAILY_SIZE,
	FULL,
	HALF,
	KINDS,
	LIVES,
	MAX_MEDICAL_CARDS,
	PATH,
	dailyDeck,
	formatPoints,
	gridLine,
	isMedicalName,
	lifelineKeep,
	livesLeft,
	points,
	runShareText,
	runStats,
	survivalDeck,
	verdictLine
} from './game-geo';

function card(kind: CardKind, i: number, name = `University ${i}`): PlayCard {
	const options =
		kind === 'country-card'
			? ['HU', 'DE', 'FR', 'ES'].map((k) => ({ key: k, label: k, lat: 0, lon: 0 }))
			: ['a', 'b', 'c', 'd'].map((k) => ({
					key: `${kind}-${i}-${k}`,
					label: `Option ${k} of ${name}`,
					lat: 0,
					lon: 0
				}));
	return {
		kind,
		semId: `${kind}-${i}`,
		name,
		prompt: name,
		options,
		answer: options[0].key,
		note: `Note ${i}.`,
		badges: [],
		lat: 0,
		lon: 0
	};
}

const fullPack: PlayCard[] = KINDS.flatMap((kind) =>
	Array.from({ length: 8 }, (_, i) => card(kind, i))
);
const countryOnly: PlayCard[] = Array.from({ length: 20 }, (_, i) => card('country-card', i));
// Every anchor carded under every kind, as the miner allows.
const sharedAnchors: PlayCard[] = KINDS.flatMap((kind) =>
	Array.from({ length: 12 }, (_, i) => ({ ...card(kind, i), semId: `inst-${i}` }))
);

function checkDeck(deck: PlayCard[], pack: PlayCard[]) {
	expect(deck).toHaveLength(DAILY_SIZE);
	expect(new Set(deck.map((c) => c.semId)).size).toBe(DAILY_SIZE);
	const ids = new Set(pack.map((c) => c.semId));
	for (const c of deck) {
		expect(ids.has(c.semId)).toBe(true);
		expect(c.options).toHaveLength(4);
		expect(c.options.map((o) => o.key)).toContain(c.answer);
	}
}

describe('dailyDeck', () => {
	it('follows the recipe when every kind has cards, deterministically per day', () => {
		const a = dailyDeck(fullPack, '2026-09-10');
		checkDeck(a, fullPack);
		expect(a.map((c) => c.kind)).toEqual(DAILY_RECIPE);
		expect(dailyDeck([...fullPack].reverse(), '2026-09-10')).toEqual(a);
		expect(dailyDeck(fullPack, '2026-09-11')).not.toEqual(a);
	});

	it('fills a short kind from the kinds that have cards', () => {
		const deck = dailyDeck(countryOnly, '2026-09-10');
		checkDeck(deck, countryOnly);
		expect(deck.every((c) => c.kind === 'country-card')).toBe(true);
		const twoNearest = [...countryOnly, card('nearest-card', 0), card('nearest-card', 1)];
		expect(
			dailyDeck(twoNearest, '2026-09-10').filter((c) => c.kind === 'nearest-card')
		).toHaveLength(2);
	});

	it('plays an anchor carded under several kinds at most once', () => {
		const deck = dailyDeck(sharedAnchors, '2026-09-10');
		checkDeck(deck, sharedAnchors);
		expect(deck.map((c) => c.kind)).toEqual(DAILY_RECIPE);
	});

	it('shifts at most one slot of a kind when a card joins mid-day', () => {
		const before = dailyDeck(countryOnly, '2026-09-10').map((c) => c.semId);
		const after = dailyDeck(
			[...countryOnly, card('country-card', 99, 'Newcomer')],
			'2026-09-10'
		).map((c) => c.semId);
		const kept = before.filter((id) => after.includes(id));
		expect(kept.length).toBeGreaterThanOrEqual(DAILY_SIZE - 1);
		expect(kept).toEqual(after.filter((id) => before.includes(id)));
	});
});

describe('survivalDeck', () => {
	it('plays every anchor once', () => {
		const deck = survivalDeck(sharedAnchors);
		expect(deck).toHaveLength(12);
		expect(new Set(deck.map((c) => c.semId)).size).toBe(12);
	});

	it('runs the whole pack with every option kept', () => {
		const deck = survivalDeck(fullPack);
		expect(deck).toHaveLength(fullPack.length);
		expect(new Set(deck.map((c) => c.semId)).size).toBe(fullPack.length);
		for (const c of deck)
			expect(c.options.map((o) => o.key).sort()).toEqual(
				fullPack
					.find((p) => p.semId === c.semId)!
					.options.map((o) => o.key)
					.sort()
			);
	});
});

describe('medical quota', () => {
	const medical = [
		'Royal Perth Hospital',
		'Hôpital Cochin',
		'Southern Medical University',
		'Austin Health'
	];
	it('recognizes hospital and medical-school names', () => {
		for (const n of medical) expect(isMedicalName(n)).toBe(true);
		expect(isMedicalName('University of Georgia')).toBe(false);
		expect(isMedicalName('Medici Institute')).toBe(false);
	});

	it('admits only a few medical names per daily', () => {
		const mixed = countryOnly.map((c, i) =>
			i % 2 ? c : { ...c, name: medical[i % medical.length] }
		);
		const deck = dailyDeck(mixed, '2026-09-10');
		expect(deck).toHaveLength(DAILY_SIZE);
		expect(deck.filter((c) => isMedicalName(c.name))).toHaveLength(MAX_MEDICAL_CARDS);
	});
});

describe('lifeline and points', () => {
	it('keeps the answer and one hashed wrong option', () => {
		const c = card('city-card', 3);
		const kept = lifelineKeep(c, '2026-09-10');
		expect(kept).toHaveLength(2);
		expect(kept[0]).toBe(c.answer);
		expect(kept[1]).not.toBe(c.answer);
		expect(lifelineKeep(c, '2026-09-10')).toEqual(kept);
	});

	it('scores a lifelined hit half, a miss nothing', () => {
		expect(points(true, false)).toBe(FULL);
		expect(points(true, true)).toBe(HALF);
		expect(points(false, true)).toBe(0);
		expect(formatPoints(15)).toBe('7½');
		expect(formatPoints(20)).toBe('10');
	});
});

describe('grid, share and verdict', () => {
	const ids = ['a', 'b', 'c', 'd'];
	it('draws one square per card', () => {
		expect(gridLine(ids, ['c'], ['b'])).toBe('🟩🟨🟥🟩');
		expect(gridLine(ids, ['b'], ['b'])).toBe('🟩🟥🟩🟩');
	});

	it('stamps the grid and the score on the share line', () => {
		const out = runShareText('2026-09-10', 15, 10, '🟩🟨🟥');
		expect(out.startsWith(`${BRAND} 2026-09-10`)).toBe(true);
		expect(out).toContain('🟩🟨🟥 7½/10');
		expect(out).toContain(`https://rankless.org${PATH}`);
	});

	it('names the perfect run, the empty one and the rest', () => {
		expect(verdictLine(20, 10)).toBe('Perfect — all 10 placed');
		expect(verdictLine(0, 10)).toBe('None of the 10 placed');
		expect(verdictLine(13, 10)).toBe('6½ of 10 placed');
	});
});

describe('livesLeft', () => {
	it('counts down from LIVES and floors at zero', () => {
		expect(livesLeft(0)).toBe(LIVES);
		expect(livesLeft(LIVES + 2)).toBe(0);
	});
});

describe('runStats', () => {
	it('summarizes the daily history into tiles and a per-point histogram', () => {
		const runs = [6, 15, 20, 0].map((score, i) => ({
			day: `2026-09-0${i + 1}`,
			score,
			outOf: 10,
			missedSemIds: [],
			lifelinedSemIds: []
		}));
		const s = runStats(runs);
		expect(s).toMatchObject({ played: 4, best: 20, avg: 5.1 });
		expect(s.hist).toHaveLength(DAILY_SIZE + 1);
		expect(s.hist[0]).toBe(1);
		expect(s.hist[3]).toBe(1);
		expect(s.hist[7]).toBe(1);
		expect(s.hist[10]).toBe(1);
		expect(runStats([])).toEqual({ played: 0, best: 0, avg: 0, hist: s.hist.map(() => 0) });
	});
});
