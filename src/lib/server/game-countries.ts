// Server side of the country game: pack reads over the MCP
// object store (`country-card` objects from pyscripts country-cards) and the
// run log. A run costs a life per miss and ends on the LIVES-th. The daily
// deck is the same for everyone (hash-ordered by day, utils/game-countries),
// practice decks are random; both cap at DECK_CAP and ship whole — the
// per-question timer is what keeps lookups out, so the client checks picks
// locally like the clue game does with its coordinates.

import { DAY_RE, gameDb, okInt, okSemIdList } from './game-common';
import { currentObjects } from './objects';
import { BE_URL } from '$lib/constants';
import { STANDING_MIN_TIER, citStandingTier, standingLabel, tierLabels } from '$lib/peers-utils';
import { urlFriendlify } from '$lib/tree-functions';
import type * as tt from '$lib/tree-types';
import { DECK_CAP, LIVES, dailyDeck, practiceDeck } from '$lib/utils/game-countries';
import type {
	BadgedCountryCard,
	CountryBadge,
	CountryCard,
	CountryPlayCard,
	CountryRunLog,
	DayStanding
} from '$lib/types/game-countries';

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

// Cards show up to this many standings; the strictest win.
const MAX_BADGES = 2;
// Enrichment fan-out per round trip, kept well under the backend's request-queue cap.
const FETCH_CHUNK = 32;
const BADGE_ROOT = 'institutions';

// Both caches live for the process, like the bundle cache: standings only move
// on a dataset change, which restarts the server anyway.
const badgeCache = new Map<string, CountryBadge[]>();
let ladderCache: { labels: string[]; rows: (number | null)[][] } | null = null;

export function currentCountryPack(): CountryCard[] {
	return currentObjects('country-card').map((o) => o.payload as CountryCard);
}

// The pack that actually serves: every card enriched with its live standings
// and gated to cards holding at least one badge — real standing is the on-card
// credibility signal. Computed at serve time with the same peers-utils
// machinery as the entity hero, so it stays current with the dataset.
export async function servedCountryPack(): Promise<BadgedCountryCard[]> {
	const pack = currentCountryPack();
	const enriched: BadgedCountryCard[] = [];
	for (let i = 0; i < pack.length; i += FETCH_CHUNK) {
		const chunk = pack.slice(i, i + FETCH_CHUNK);
		const badges = await Promise.all(chunk.map((c) => badgesFor(c.semId)));
		chunk.forEach((c, j) => enriched.push({ ...c, badges: badges[j] }));
	}
	return enriched.filter((c) => c.badges.length > 0);
}

// Strongest standings of one institution, strictest first; [] when the backend
// has no peers profile for it. Only resolved values are cached, so a transient
// backend failure throws without poisoning the cache.
export async function badgesFor(semId: string): Promise<CountryBadge[]> {
	const hit = badgeCache.get(semId);
	if (hit) return hit;
	const [ladder, peers] = await Promise.all([getLadder(), getPeers(semId)]);
	const badges = peers
		? peers.topSubfields
				.map((sf, i) => ({
					tier: citStandingTier(ladder.rows[sf.dmId] ?? [], peers.hero.subfieldCitations[i] ?? 0),
					cits: peers.hero.subfieldCitations[i] ?? 0,
					subfield: sf.name
				}))
				.filter((s) => s.tier >= STANDING_MIN_TIER)
				.sort((a, b) => b.tier - a.tier || b.cits - a.cits)
				.slice(0, MAX_BADGES)
				.map((s) => ({ label: standingLabel(s.tier, ladder.labels) ?? '', subfield: s.subfield }))
		: [];
	badgeCache.set(semId, badges);
	return badges;
}

export async function servedDailyDeck(day: string): Promise<CountryPlayCard[]> {
	return dailyDeck(await servedCountryPack(), day);
}

export async function servedPracticeDeck(): Promise<CountryPlayCard[]> {
	return practiceDeck(await servedCountryPack());
}

async function getLadder(): Promise<NonNullable<typeof ladderCache>> {
	if (ladderCache) return ladderCache;
	const res = await fetch(`${BE_URL}/ladder/${BADGE_ROOT}`);
	if (!res.ok) throw new Error(`ladder fetch failed: ${res.status}`);
	const data = (await res.json()) as tt.LadderData;
	ladderCache = { labels: tierLabels(data.pctBands), rows: data.ladder };
	return ladderCache;
}

async function getPeers(semId: string): Promise<tt.EntityPeersResp | null> {
	const res = await fetch(`${BE_URL}/peers/${BADGE_ROOT}/${urlFriendlify(semId)}`);
	if (res.status === 404) return null;
	if (!res.ok) throw new Error(`peers fetch failed for ${semId}: ${res.status}`);
	return (await res.json()) as tt.EntityPeersResp;
}

// Logs the run and, for a daily one, answers with its standing among the
// day's runs so far (the just-logged run included).
export function recordRun(run: CountryRunLog, orcid: string | null): DayStanding | null {
	const d = gameDb(COUNTRY_SCHEMA);
	d.prepare(
		`INSERT INTO country_game_results (mode, day, score, out_of, missed_sem_ids, orcid)
		 VALUES (?, ?, ?, ?, ?, ?)`
	).run(run.mode, run.day, run.score, run.outOf, JSON.stringify(run.missedSemIds), orcid);
	if (run.mode !== 'daily') return null;
	const row = d
		.prepare(
			`SELECT count(*) AS players, sum(score > ?) AS above
			 FROM country_game_results WHERE mode = 'daily' AND day = ?`
		)
		.get(run.score, run.day) as { players: number; above: number };
	return { rank: row.above + 1, players: row.players };
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
