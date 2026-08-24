// Server side of the clue-ladder game: pack reads over the MCP object store and
// the play-result log. Cards ship to the browser one at a time (daily via the
// page load, practice via GET /api/game-clues) with verification facts stripped.

import { DAY_RE, SEM_ID_RE, gameDb, okInt, okNullNum } from './game-common';
import { currentObjects } from './objects';
import { dailyIndex } from '$lib/utils/game';
import type { GameCard, GameResultLog, PlayCard } from '$lib/types/game-clues';

// The etype whose game-card pack /game-clues serves.
export const GAME_PACK_ETYPE = 'institutions';

const GAME_SCHEMA = `
CREATE TABLE IF NOT EXISTS game_results (
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	mode TEXT NOT NULL,
	day TEXT NOT NULL,
	sem_id TEXT NOT NULL,
	clues_used INTEGER NOT NULL,
	gave_up INTEGER NOT NULL,
	guess_lat REAL,
	guess_lon REAL,
	distance_km REAL,
	score INTEGER NOT NULL,
	orcid TEXT,
	created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_gr_day ON game_results(day);
CREATE TABLE IF NOT EXISTS game_daily (
	day TEXT PRIMARY KEY,
	sem_id TEXT NOT NULL,
	created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
`;

let dailyPin: { day: string; semId: string } | null = null;

// Sorted for a stable daily pick across boxes.
export function currentPack(): GameCard[] {
	return currentObjects('game-card')
		.filter((o) => o.etype === GAME_PACK_ETYPE)
		.map((o) => o.payload as GameCard)
		.sort((a, b) => a.semId.localeCompare(b.semId));
}

// The day's card is pinned in game_daily so the pick survives pack growth and
// rides the cross-box merge; the current day's pin is also held in memory, so
// steady-state serving never queries the table. A pin whose card left the pack
// (rejected mid-day) is re-pinned; the replacement pick is deterministic, so
// every worker converges on the same card.
export function dailyCard(day: string, pack: GameCard[] = currentPack()): PlayCard | null {
	if (!pack.length) return null;
	let card = dailyPin?.day === day ? pack.find((c) => c.semId === dailyPin?.semId) : undefined;
	if (!card) {
		card = pinnedDaily(day, pack);
		dailyPin = { day, semId: card.semId };
	}
	return toPlayCard(card);
}

function pinnedDaily(day: string, pack: GameCard[]): GameCard {
	const db = gameDb(GAME_SCHEMA);
	const row = db.prepare('SELECT sem_id FROM game_daily WHERE day = ?').get(day) as {
		sem_id: string;
	} | null;
	const pinned = row && pack.find((c) => c.semId === row.sem_id);
	if (pinned) return pinned;
	const pick = pack[dailyIndex(day, pack.length)];
	db.prepare(
		'INSERT INTO game_daily (day, sem_id) VALUES (?, ?) ON CONFLICT(day) DO UPDATE SET sem_id = excluded.sem_id'
	).run(day, pick.semId);
	return pick;
}

// Random card for a practice round, avoiding `exclude` when the pack allows it.
export function practiceCard(exclude: string | null): PlayCard | null {
	const pack = currentPack();
	if (!pack.length) return null;
	const pool = pack.filter((c) => c.semId !== exclude);
	const cards = pool.length ? pool : pack;
	return toPlayCard(cards[Math.floor(Math.random() * cards.length)]);
}

export function recordResult(result: GameResultLog, orcid: string | null): void {
	gameDb(GAME_SCHEMA)
		.prepare(
			`INSERT INTO game_results
			 (mode, day, sem_id, clues_used, gave_up, guess_lat, guess_lon, distance_km, score, orcid)
			 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
		)
		.run(
			result.mode,
			result.day,
			result.semId,
			result.cluesUsed,
			result.gaveUp ? 1 : 0,
			result.guessLat,
			result.guessLon,
			result.distanceKm,
			result.score,
			orcid
		);
}

// Boundary validation of a posted result: the endpoint is public, so every
// field is checked for type and plausible range before it touches the DB.
export function parseResult(raw: unknown): GameResultLog | null {
	if (typeof raw !== 'object' || raw === null) return null;
	const r = raw as Record<string, unknown>;
	if (
		(r.mode !== 'daily' && r.mode !== 'practice') ||
		typeof r.day !== 'string' ||
		!DAY_RE.test(r.day) ||
		typeof r.semId !== 'string' ||
		!SEM_ID_RE.test(r.semId) ||
		!okInt(r.cluesUsed, 1, 12) ||
		typeof r.gaveUp !== 'boolean' ||
		!okNullNum(r.guessLat, -90, 90) ||
		!okNullNum(r.guessLon, -180, 180) ||
		!okNullNum(r.distanceKm, 0, 21000) ||
		!okInt(r.score, 0, 1000)
	)
		return null;
	return {
		mode: r.mode,
		day: r.day,
		semId: r.semId,
		cluesUsed: r.cluesUsed as number,
		gaveUp: r.gaveUp,
		guessLat: r.guessLat as number | null,
		guessLon: r.guessLon as number | null,
		distanceKm: r.distanceKm as number | null,
		score: r.score as number
	};
}

function toPlayCard(card: GameCard): PlayCard {
	return { ...card, clues: card.clues.map(({ stage, text }) => ({ stage, text })) };
}
