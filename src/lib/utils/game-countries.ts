// Client-side rules for the country game (/game-countries): lives, the
// per-question timer that keeps lookups out, and the share line. Shared game
// plumbing is in utils/game.ts, types in types/game-countries.ts.

import { shareMessage, shuffle } from './game';
import type { BadgedCountryCard, CountryPlayCard } from '../types/game-countries';

export const RUN_SECONDS = 10;
export const DECK_CAP = 30;
export const LIVES = 3;
// Post-answer beat before the next card: long enough to register the flash.
export const ADVANCE_MS = 700;

export function livesLeft(missed: number): number {
	return Math.max(0, LIVES - missed);
}

export function runShareText(day: string, score: number, missed: number, swept: boolean): string {
	const hearts = '❤️'.repeat(livesLeft(missed)) + '🖤'.repeat(Math.min(missed, LIVES));
	const result = swept ? `cleared the deck — ${score} placed` : `${score} placed`;
	return shareMessage(day, `🏛️🌍 ${result} ${hearts}`, '/game-countries');
}

// Every deck is a fresh random draw over the pack — deck order and each
// card's option order alike; no run is replayable for lookups.
export function buildDeck(pack: BadgedCountryCard[]): CountryPlayCard[] {
	return shuffle(pack)
		.slice(0, DECK_CAP)
		.map((c) => ({
			semId: c.semId,
			name: c.name,
			cc: c.cc,
			note: c.note,
			badges: c.badges,
			options: shuffle([c.cc, ...c.decoys])
		}));
}
