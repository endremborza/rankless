// Client-side rules for the country game (/game-countries): the per-question
// timer that keeps lookups out, and the share line. Shared game plumbing is in
// utils/game.ts, types in types/game-countries.ts.

import { shareMessage, shuffle } from './game';
import type { CountryCard, CountryPlayCard } from '../types/game-countries';

export const RUN_SECONDS = 10;
export const DECK_CAP = 30;
// Post-answer beat before the next card: long enough to register the flash.
export const ADVANCE_MS = 700;

export function runShareText(day: string, score: number, outOf: number): string {
	const result = score >= outOf ? `swept all ${outOf} 🏆` : `${score}/${outOf} before a miss`;
	return shareMessage(day, `🏛️⏱️ ${result}`, '/game-countries');
}

// Every deck is a fresh random draw over the pack — deck order and each
// card's option order alike; no run is replayable for lookups.
export function buildDeck(pack: CountryCard[]): CountryPlayCard[] {
	return shuffle(pack)
		.slice(0, DECK_CAP)
		.map((c) => ({
			semId: c.semId,
			name: c.name,
			cc: c.cc,
			note: c.note,
			options: shuffle([c.cc, ...c.decoys])
		}));
}
