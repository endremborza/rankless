// Server side of the guessing game: pack reads over the MCP object store and
// the play-result log. Cards ship to the browser one at a time (daily via the
// page load, practice via GET /api/game) with verification facts stripped.

import { getDb } from './db';
import { currentObjects } from './objects';
import { dailyIndex } from '$lib/utils/game';
import type { GameCard, GameResultLog, PlayCard } from '$lib/types/game';

// Which pack the /game route plays. Flip (or branch on a route param) when a
// second pack — e.g. countries — is ready to serve.
export const GAME_PACK_ETYPE = 'institutions';

const RESULTS_SCHEMA = `
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
`;

const SEM_ID_RE = /^[\w.-]{1,80}$/;

let ensured = false;

// Sorted for a stable daily pick across boxes.
export function currentPack(): GameCard[] {
	return currentObjects('game-card')
		.filter((o) => o.etype === GAME_PACK_ETYPE)
		.map((o) => o.payload as GameCard)
		.sort((a, b) => a.semId.localeCompare(b.semId));
}

export function dailyCard(day: string): PlayCard | null {
	const pack = currentPack();
	if (!pack.length) return null;
	return toPlayCard(pack[dailyIndex(day, pack.length)]);
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
	resultsDb()
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
	const okNum = (v: unknown, lo: number, hi: number) =>
		typeof v === 'number' && Number.isFinite(v) && v >= lo && v <= hi;
	const okNullNum = (v: unknown, lo: number, hi: number) => v === null || okNum(v, lo, hi);
	if (
		(r.mode !== 'daily' && r.mode !== 'practice') ||
		typeof r.day !== 'string' ||
		!/^\d{4}-\d{2}-\d{2}$/.test(r.day) ||
		typeof r.semId !== 'string' ||
		!SEM_ID_RE.test(r.semId) ||
		!Number.isInteger(r.cluesUsed) ||
		!okNum(r.cluesUsed, 1, 12) ||
		typeof r.gaveUp !== 'boolean' ||
		!okNullNum(r.guessLat, -90, 90) ||
		!okNullNum(r.guessLon, -180, 180) ||
		!okNullNum(r.distanceKm, 0, 21000) ||
		!Number.isInteger(r.score) ||
		!okNum(r.score, 0, 1000)
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

function resultsDb() {
	const d = getDb();
	if (!ensured) {
		d.run(RESULTS_SCHEMA);
		ensured = true;
	}
	return d;
}
