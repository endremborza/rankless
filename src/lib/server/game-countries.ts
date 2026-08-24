// Server side of the country game (/game-countries): pack reads over the MCP
// object store (`country-card` objects from pyscripts country-cards) and the
// run log. A run is sudden-death: every deck is a fresh random shuffle of the
// pack, capped at DECK_CAP cards, and the whole deck ships at once — the
// per-question timer is what keeps lookups out, so the client checks picks
// locally like the clue game does with its coordinates.

import { DAY_RE, SEM_ID_RE, gameDb, okInt } from './game-common';
import { currentObjects } from './objects';
import { DECK_CAP, buildDeck } from '$lib/utils/game-countries';
import type { CountryCard, CountryPlayCard, CountryRunLog } from '$lib/types/game-countries';

const COUNTRY_SCHEMA = `
CREATE TABLE IF NOT EXISTS country_game_results (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	mode TEXT NOT NULL,
	day TEXT NOT NULL,
	score INTEGER NOT NULL,
	out_of INTEGER NOT NULL,
	failed_sem_id TEXT,
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
			`INSERT INTO country_game_results (mode, day, score, out_of, failed_sem_id, orcid)
			 VALUES (?, ?, ?, ?, ?, ?)`
		)
		.run(run.mode, run.day, run.score, run.outOf, run.failedSemId, orcid);
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
		(r.failedSemId !== null &&
			(typeof r.failedSemId !== 'string' || !SEM_ID_RE.test(r.failedSemId)))
	)
		return null;
	return {
		mode: r.mode,
		day: r.day,
		score: r.score as number,
		outOf: r.outOf as number,
		failedSemId: r.failedSemId as string | null
	};
}
