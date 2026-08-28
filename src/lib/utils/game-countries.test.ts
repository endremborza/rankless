import { describe, expect, it } from 'vitest';

import type { BadgedCountryCard } from '../types/game-countries';
import { DECK_CAP, LIVES, buildDeck, livesLeft, runShareText } from './game-countries';

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
			expect(card.badges).toEqual([{ label: 'top 10%', subfield: 'Immunology' }]);
			expect(card).not.toHaveProperty('decoys');
			expect(card).not.toHaveProperty('papers');
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

describe('runShareText', () => {
	it('shows the score, the lives spent, and a cleared deck', () => {
		const out = runShareText('2026-08-23', 12, 2, false);
		expect(out).toContain('12 placed');
		expect(out).toContain('❤️'.repeat(LIVES - 2) + '🖤'.repeat(2));
		expect(out).toContain('https://rankless.org/game-countries');

		expect(runShareText('2026-08-23', 30, 0, true)).toContain('cleared the deck');
		expect(runShareText('2026-08-23', 30, 0, true)).toContain('❤️'.repeat(LIVES));
	});
});
