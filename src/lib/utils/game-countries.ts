// Client-side rules for the country game: lives, the per-question timer that
// keeps lookups out, deck builds, the share line and the personal stats.
// Shared game plumbing is in utils/game.ts, types in types/game-countries.ts.

import { fnv1a, shareMessage, shuffle } from './game';
import type {
	BadgedCountryCard,
	CountryPlayCard,
	DailyRun,
	RunStats
} from '../types/game-countries';

// Public identity of the game, and the only place a rename touches: the route
// directory matches on SLUG (src/params/campusQuest.ts) instead of naming it,
// and links, share lines and specs read PATH. Module names, storage keys, API
// routes and tables stay name-agnostic.
export const BRAND = 'CampusQuest';
export const SLUG = 'campus-quest';
export const PATH = `/${SLUG}`;
export const RUN_SECONDS = 10;
export const DECK_CAP = 30;
export const LIVES = 3;
// Hospitals and medical schools are a quarter of the pack; a deck admits only
// a few so a run reads as institutions, not wards.
export const MAX_MEDICAL_CARDS = 3;
const MEDICAL_RE =
	/\b(hospitals?|hôpital|hopital|ospedale|hospice|clinics?|clínic|klinik|infirmary|medicine|medical|health|sjukhus|sairaala|sygehus|ziekenhuis|krankenhaus)\b/i;
// Score histogram buckets of the stats sheet: [lo, hi] inclusive, the last one
// absorbing the deck cap.
export const HIST_STEP = 5;
export const HIST_BUCKETS: [number, number][] = Array.from(
	{ length: DECK_CAP / HIST_STEP },
	(_, i) => [i * HIST_STEP, i === DECK_CAP / HIST_STEP - 1 ? DECK_CAP : (i + 1) * HIST_STEP - 1]
);

export function livesLeft(missed: number): number {
	return Math.max(0, LIVES - missed);
}

export function isMedicalName(name: string): boolean {
	return MEDICAL_RE.test(name);
}

export function runShareText(day: string, score: number, missed: number, swept: boolean): string {
	const hearts = '❤️'.repeat(livesLeft(missed)) + '🖤'.repeat(Math.min(missed, LIVES));
	const result = swept ? `cleared the deck — ${score} placed` : `${score} placed`;
	return shareMessage(BRAND, day, `🏛️🌍 ${result} ${hearts}`, PATH);
}

export function verdictLine(score: number, missed: number, outOf: number): string {
	const seen = score + missed;
	if (seen < outOf) return `Run over at card ${seen} of ${outOf}`;
	return missed === 0 ? `Perfect run — all ${outOf} placed` : `Cleared the deck — ${outOf} names`;
}

// The daily deck is the same for every player: cards rank by a hash of the
// day and their id (rendezvous order), so the pick is deterministic without a
// pin table and a card added or pulled mid-day shifts at most one slot. Option
// order hashes the same way. The per-question timer is what keeps lookups out.
export function dailyDeck(pack: BadgedCountryCard[], day: string): CountryPlayCard[] {
	const key = (s: string) => fnv1a(`${day}|${s}`);
	return admit([...pack].sort((a, b) => key(a.semId) - key(b.semId))).map((c) =>
		playCard(
			c,
			[c.cc, ...c.decoys].sort((a, b) => key(`${c.semId}|${a}`) - key(`${c.semId}|${b}`))
		)
	);
}

// Practice decks are a fresh random draw over the pack — deck order and each
// card's option order alike.
export function practiceDeck(pack: BadgedCountryCard[]): CountryPlayCard[] {
	return admit(shuffle(pack)).map((c) => playCard(c, shuffle([c.cc, ...c.decoys])));
}

export function runStats(runs: DailyRun[]): RunStats {
	const hist = HIST_BUCKETS.map(() => 0);
	let total = 0;
	let best = 0;
	for (const r of runs) {
		hist[Math.min(Math.floor(r.score / HIST_STEP), hist.length - 1)] += 1;
		total += r.score;
		best = Math.max(best, r.score);
	}
	const avg = runs.length ? Math.round((total / runs.length) * 10) / 10 : 0;
	return { played: runs.length, best, avg, hist };
}

// Walks an ordered pack into a deck: the first DECK_CAP cards, medical names
// beyond their quota skipped.
function admit(ordered: BadgedCountryCard[]): BadgedCountryCard[] {
	const deck: BadgedCountryCard[] = [];
	let medical = 0;
	for (const c of ordered) {
		if (deck.length === DECK_CAP) break;
		if (isMedicalName(c.name)) {
			if (medical === MAX_MEDICAL_CARDS) continue;
			medical += 1;
		}
		deck.push(c);
	}
	return deck;
}

function playCard(c: BadgedCountryCard, options: string[]): CountryPlayCard {
	return { semId: c.semId, name: c.name, cc: c.cc, note: c.note, badges: c.badges, options };
}
