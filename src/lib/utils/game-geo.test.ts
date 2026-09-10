import { describe, expect, it } from 'vitest';

import type { BadgedCountryCard } from '../types/game-countries';
import {
	BRAND,
	DECK_CAP,
	HIST_BUCKETS,
	LIVES,
	MAX_MEDICAL_CARDS,
	PATH,
	dailyDeck,
	isMedicalName,
	livesLeft,
	practiceDeck,
	runShareText,
	runStats,
	verdictLine
} from './game-countries';

const pack: BadgedCountryCard[] = Array.from({ length: DECK_CAP + 10 }, (_, i) => ({
	semId: `uni-${i}`,
	name: `University ${i}`,
	cc: 'HU',
	decoys: ['DE', 'FR', 'ES'],
	note: `Note ${i}.`,
	badges: [{ label: 'top 10%', subfield: 'Immunology' }],
	papers: 1,
	citations: 1
}));

function checkPlayCards(deck: ReturnType<typeof practiceDeck>) {
	expect(deck).toHaveLength(DECK_CAP);
	const semIds = new Set(pack.map((c) => c.semId));
	expect(new Set(deck.map((c) => c.semId)).size).toBe(DECK_CAP);
	for (const card of deck) {
		expect(semIds.has(card.semId)).toBe(true);
		expect(card.options).toHaveLength(4);
		expect(card.options).toContain(card.cc);
		expect(new Set(card.options).size).toBe(4);
		expect(card.badges).toEqual([{ label: 'top 10%', subfield: 'Immunology' }]);
		expect(card).not.toHaveProperty('decoys');
		expect(card).not.toHaveProperty('papers');
	}
}

describe('practiceDeck', () => {
	it('caps the deck, draws from the pack and folds the answer into four options', () => {
		checkPlayCards(practiceDeck(pack));
	});
});

describe('dailyDeck', () => {
	it('builds the same play cards for the same day, whatever the pack order', () => {
		const a = dailyDeck(pack, '2026-08-31');
		checkPlayCards(a);
		expect(dailyDeck([...pack].reverse(), '2026-08-31')).toEqual(a);
		expect(dailyDeck(pack, '2026-09-01')).not.toEqual(a);
	});

	it('shifts at most one slot when a card joins the pack mid-day', () => {
		const before = dailyDeck(pack, '2026-08-31').map((c) => c.semId);
		const after = dailyDeck(
			[...pack, { ...pack[0], semId: 'newcomer', name: 'Newcomer' }],
			'2026-08-31'
		).map((c) => c.semId);
		const kept = before.filter((id) => after.includes(id));
		expect(kept.length).toBeGreaterThanOrEqual(DECK_CAP - 1);
		expect(kept).toEqual(after.filter((id) => before.includes(id)));
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

	it('admits only a few medical names per deck, daily and practice alike', () => {
		const mixed = pack.map((c, i) => (i % 4 ? c : { ...c, name: medical[i % medical.length] }));
		for (const deck of [dailyDeck(mixed, '2026-08-31'), practiceDeck(mixed)]) {
			expect(deck).toHaveLength(DECK_CAP);
			expect(deck.filter((c) => isMedicalName(c.name))).toHaveLength(MAX_MEDICAL_CARDS);
		}
	});
});

describe('livesLeft', () => {
	it('counts down from LIVES and floors at zero', () => {
		expect(livesLeft(0)).toBe(LIVES);
		expect(livesLeft(1)).toBe(LIVES - 1);
		expect(livesLeft(LIVES)).toBe(0);
		expect(livesLeft(LIVES + 2)).toBe(0);
	});
});

describe('verdictLine', () => {
	it('names the card that ended the run, or the sweep', () => {
		expect(verdictLine(7, 3, 30)).toBe('Run over at card 10 of 30');
		expect(verdictLine(30, 0, 30)).toBe('Perfect run — all 30 placed');
		expect(verdictLine(28, 2, 30)).toBe('Cleared the deck — 30 names');
	});
});

describe('runStats', () => {
	it('summarizes the daily history into tiles and a score histogram', () => {
		const runs = [3, 12, 30, 0].map((score, i) => ({
			day: `2026-08-0${i + 1}`,
			score,
			outOf: 30,
			missedIds: []
		}));
		const s = runStats(runs);
		expect(s).toMatchObject({ played: 4, best: 30, avg: 11.3 });
		expect(s.hist).toHaveLength(HIST_BUCKETS.length);
		expect(s.hist.reduce((a, b) => a + b)).toBe(4);
		expect(s.hist[0]).toBe(2);
		expect(s.hist[s.hist.length - 1]).toBe(1);
		expect(HIST_BUCKETS[HIST_BUCKETS.length - 1][1]).toBe(DECK_CAP);
		expect(runStats([])).toEqual({ played: 0, best: 0, avg: 0, hist: s.hist.map(() => 0) });
	});
});

describe('runShareText', () => {
	it('shows the score, the lives spent, and a cleared deck', () => {
		const out = runShareText('2026-08-23', 12, 2, false);
		expect(out.startsWith(`${BRAND} 2026-08-23`)).toBe(true);
		expect(out).toContain('12 placed');
		expect(out).toContain('❤️'.repeat(LIVES - 2) + '🖤'.repeat(2));
		expect(out).toContain(`https://rankless.org${PATH}`);

		expect(runShareText('2026-08-23', 30, 0, true)).toContain('cleared the deck');
		expect(runShareText('2026-08-23', 30, 0, true)).toContain('❤️'.repeat(LIVES));
	});
});
