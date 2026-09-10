// Server side of the geography quiz: pack reads over the MCP object store
// (one object kind per question pair, written by pyscripts
// rankless-game-card-mining), the play-card shape every kind folds into, and
// the run log. The daily deck is the same for everyone (recipe over the
// hash order of the day, utils/game-geo), survival decks are random; both
// ship whole — the per-question timer is what keeps lookups out, so the
// client checks picks locally.

import { DAY_RE, okInt, okSemIdList } from './game-common';
import { getDb } from './db';
import { currentObjects } from './objects';
import { BE_URL } from '$lib/constants';
import { STANDING_MIN_TIER, citStandingTier, standingLabel, tierLabels } from '$lib/peers-utils';
import { encodeSemanticId } from '$lib/tree-functions';
import type * as tt from '$lib/tree-types';
import { FULL, KINDS, dailyDeck, survivalDeck } from '$lib/utils/game-geo';
import type {
	CardBadge,
	DayStanding,
	PlayCard,
	PlayOption,
	RunLog,
	StoredCard
} from '$lib/types/game-geo';

// Cards show up to this many standings; the strictest win.
const MAX_BADGES = 2;
// Enrichment fan-out per round trip, kept well under the backend's request-queue cap.
const FETCH_CHUNK = 32;
const BADGE_ROOT = 'institutions';
// Bound on a logged deck size (survival runs the whole pack), not a rule.
const MAX_OUT_OF = 5000;

// Both caches live for the process, like the bundle cache: standings only move
// on a dataset change, which restarts the server anyway.
const badgeCache = new Map<string, CardBadge[]>();
let ladderCache: { labels: string[]; rows: (number | null)[][] } | null = null;

export function currentPack(): StoredCard[] {
	return KINDS.flatMap((kind) =>
		currentObjects(kind).map((o) => ({ kind, payload: o.payload }) as StoredCard)
	);
}

// The pack that actually serves. Country cards are enriched with their live
// standings and gated to cards holding at least one badge — real standing is
// the on-card credibility signal for a name meant to mislead; the generated
// kinds carry their answer's evidence in the card itself and show none.
export async function servedPack(): Promise<PlayCard[]> {
	const pack = currentPack();
	const served: PlayCard[] = [];
	for (let i = 0; i < pack.length; i += FETCH_CHUNK) {
		const chunk = pack.slice(i, i + FETCH_CHUNK);
		const badges = await Promise.all(
			chunk.map((c) => (c.kind === 'country-card' ? badgesFor(c.payload.semId) : []))
		);
		chunk.forEach((c, j) => {
			if (c.kind !== 'country-card' || badges[j].length) served.push(toPlayCard(c, badges[j]));
		});
	}
	return served;
}

// One play shape for every kind: the prompt and the option keys/labels the
// kind's question reads, the answer recomputed from the stored evidence.
export function toPlayCard(card: StoredCard, badges: CardBadge[]): PlayCard {
	const p = card.payload;
	const base = {
		kind: card.kind,
		semId: p.semId,
		name: p.name,
		note: p.note,
		badges,
		lat: 0,
		lon: 0
	};
	const inst = (o: { semId: string; name: string }): PlayOption => ({
		key: o.semId,
		label: o.name,
		lat: 0,
		lon: 0
	});
	// "Where/which city is <anchor>?": the answer is a place, the decoys are places.
	const placeOf = (answer: string, decoys: string[]): PlayCard => ({
		...base,
		prompt: p.name,
		options: [answer, ...decoys].map(plain),
		answer
	});
	// "Which one is (not) in <place>?": the anchor is the answer among institutions.
	const anchorIn = (place: string, options: { semId: string; name: string }[]): PlayCard => ({
		...base,
		prompt: place,
		options: [inst(p), ...options.map(inst)],
		answer: p.semId
	});
	switch (card.kind) {
		case 'country-card':
			return placeOf(card.payload.cc, card.payload.decoys);
		case 'city-card':
			return placeOf(card.payload.city, card.payload.decoys);
		case 'nearest-card': {
			const { options, lat, lon } = card.payload;
			const nearest = options.reduce((a, b) => (b.km < a.km ? b : a));
			return {
				...base,
				lat,
				lon,
				prompt: p.name,
				options: options.map((o) => ({ ...inst(o), lat: o.lat, lon: o.lon, km: o.km })),
				answer: nearest.semId
			};
		}
		case 'intruder-card':
			return anchorIn(card.payload.country, card.payload.options);
		case 'local-card':
			return anchorIn(card.payload.city, card.payload.options);
	}
}

// Strongest standings of one institution, strictest first; [] when the backend
// has no peers profile for it. Only resolved values are cached, so a transient
// backend failure throws without poisoning the cache.
export async function badgesFor(semId: string): Promise<CardBadge[]> {
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
	const res = await fetch(`${BE_URL}/peers/${BADGE_ROOT}/${encodeSemanticId(semId)}`);
	if (res.status === 404) return null;
	if (!res.ok) throw new Error(`peers fetch failed for ${semId}: ${res.status}`);
	return (await res.json()) as tt.EntityPeersResp;
}

// Logs the run and, for a daily one, answers with its standing among the
// day's runs so far (the just-logged run included).
export function recordRun(run: CountryRunLog, orcid: string | null): DayStanding | null {
	const d = getDb();
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
export function parseRun(raw: unknown): RunLog | null {
	if (typeof raw !== 'object' || raw === null) return null;
	const r = raw as Record<string, unknown>;
	if (
		(r.mode !== 'daily' && r.mode !== 'survival') ||
		typeof r.day !== 'string' ||
		!DAY_RE.test(r.day) ||
		!okInt(r.outOf, 1, MAX_OUT_OF) ||
		!okSemIdList(r.missedSemIds, r.outOf as number) ||
		!okSemIdList(r.lifelinedSemIds, r.outOf as number) ||
		// every card seen was placed or missed, and a placed card is worth FULL at most
		!okInt(r.score, 0, ((r.outOf as number) - r.missedSemIds.length) * FULL)
	)
		return null;
	return {
		mode: r.mode,
		day: r.day,
		score: r.score as number,
		outOf: r.outOf as number,
		missedSemIds: r.missedSemIds,
		lifelinedSemIds: r.lifelinedSemIds
	};
}

function plain(key: string): PlayOption {
	return { key, label: key, lat: 0, lon: 0 };
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
	const res = await fetch(`${BE_URL}/peers/${BADGE_ROOT}/${encodeSemanticId(semId)}`);
	if (res.status === 404) return null;
	if (!res.ok) throw new Error(`peers fetch failed for ${semId}: ${res.status}`);
	return (await res.json()) as tt.EntityPeersResp;
}
