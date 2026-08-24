import { describe, expect, it } from 'vitest';

import type { CountryCard } from '../types/game-countries';
import { DECK_CAP, buildDeck, runShareText } from './game-countries';

const pack: CountryCard[] = Array.from({ length: DECK_CAP + 10 }, (_, i) => ({
	semId: `uni-${i}`,
	name: `University ${i}`,
	cc: 'HU',
	decoys: ['DE', 'FR', 'ES'],
	note: `Note ${i}.`,
	papers: 1,
	citations: 1
}));

describe('buildDeck', () => {
	it('caps the deck and draws every card from the pack', () => {
		const a = buildDeck(pack);
		expect(a).toHaveLength(DECK_CAP);
		const semIds = new Set(pack.map((c) => c.semId));
		expect(new Set(a.map((c) => c.semId)).size).toBe(DECK_CAP);
		for (const card of a) expect(semIds.has(card.semId)).toBe(true);
	});

	it('folds the answer into four shuffled options and drops the decoy list', () => {
		for (const card of buildDeck(pack)) {
			expect(card.options).toHaveLength(4);
			expect(card.options).toContain(card.cc);
			expect(new Set(card.options).size).toBe(4);
			expect(card).not.toHaveProperty('decoys');
			expect(card).not.toHaveProperty('papers');
		}
	});
});

describe('runShareText', () => {
	it('reports a miss score and celebrates a sweep', () => {
		expect(runShareText('2026-08-23', 4, 30)).toContain('4/30 before a miss');
		expect(runShareText('2026-08-23', 30, 30)).toContain('swept all 30');
		expect(runShareText('2026-08-23', 4, 30)).toContain('https://rankless.org/game-countries');
	});
});
