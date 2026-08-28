// Server side of the country game (/game-homeground): pack reads over the MCP
// object store (`country-card` objects from pyscripts country-cards) and the
// run log. A run costs a life per miss and ends on the LIVES-th: every deck is
// a fresh random shuffle of the pack, capped at DECK_CAP cards, and the whole
// deck ships at once — the per-question timer is what keeps lookups out, so the
// client checks picks locally like the clue game does with its coordinates.

import { DAY_RE, gameDb, okInt, okSemIdList } from './game-common';
import { currentObjects } from './objects';
import { DECK_CAP, LIVES, buildDeck } from '$lib/utils/game-countries';
import type { CountryCard, CountryPlayCard, CountryRunLog } from '$lib/types/game-countries';

// `missed_sem_ids` is a JSON array — one run costs up to LIVES cards, and every
// one of them is difficulty signal for the card pack.
const COUNTRY_SCHEMA = `
CREATE TABLE IF NOT EXISTS country_game_results (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	mode TEXT NOT NULL,
	day TEXT NOT NULL,
	score INTEGER NOT NULL,
	out_of INTEGER NOT NULL,
	missed_sem_ids TEXT,
	orcid TEXT,
	created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_cgr_day ON country_game_results(day);
`;

export function currentCountryPack(): CountryCard[] {
	return currentObjects('country-card').map((o) => o.payload as CountryCard);
}

export function newDeck(): CountryPlayCard[] {
	return buildDeck(currentCountryPack());
}

export function recordRun(run: CountryRunLog, orcid: string | null): void {
	gameDb(COUNTRY_SCHEMA)
		.prepare(
			`INSERT INTO country_game_results (mode, day, score, out_of, missed_sem_ids, orcid)
			 VALUES (?, ?, ?, ?, ?, ?)`
		)
		.run(run.mode, run.day, run.score, run.outOf, JSON.stringify(run.missedSemIds), orcid);
}

// Boundary validation of a posted run: the endpoint is public, so every field
// is checked for type and plausible range before it touches the DB.
export function parseRun(raw: unknown): CountryRunLog | null {
	if (typeof raw !== 'object' || raw === null) return null;
	const r = raw as Record<string, unknown>;
	if (
		(r.mode !== 'daily' && r.mode !== 'practice') ||
		typeof r.day !== 'string' ||
		!DAY_RE.test(r.day) ||
		!okInt(r.outOf, 1, DECK_CAP) ||
		!okInt(r.score, 0, r.outOf as number) ||
		!okSemIdList(r.missedSemIds, LIVES) ||
		// every card seen was either placed or missed, so the two must fit the deck
		(r.score as number) + (r.missedSemIds as string[]).length > (r.outOf as number)
	)
		return null;
	return {
		mode: r.mode,
		day: r.day,
		score: r.score as number,
		outOf: r.outOf as number,
		missedSemIds: r.missedSemIds as string[]
	};
}
