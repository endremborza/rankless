// Geography-quiz card shapes. Source of truth: pyscripts/explore/game_card_mining.py
// writes one object kind per question pair into the MCP object store; every
// card's `facts` are the reproduced backend place and coordinate reads the
// answer was computed from (the model states no numbers, so `claimed` is null).

import type { LatLon } from '$lib/utils/geo';
import type { VerifiedFact } from './mcp';

export type CardKind =
	| 'country-card'
	| 'intruder-card'
	| 'nearest-card'
	| 'city-card'
	| 'local-card';

export type GameFact = VerifiedFact;

// Every card is keyed by its anchor institution (`semId`); `cc` is the
// anchor's country for the per-country cap, `city` its city. `facts` is
// optional on country cards.
type CardBase = {
	semId: string;
	name: string;
	cc: string;
	city: string;
	note: string;
	papers: number;
	citations: number;
	facts?: GameFact[];
};

type OptionInst = { semId: string; name: string; cc: string };

export type CountryCardPayload = CardBase & { decoys: string[] };
export type CityCardPayload = CardBase & { decoys: string[] };
export type NearestCardPayload = CardBase &
	LatLon & { options: (OptionInst & LatLon & { km: number })[] };
export type IntruderCardPayload = CardBase & { country: string; options: OptionInst[] };
export type LocalCardPayload = CardBase & { options: (OptionInst & { city: string })[] };

export type StoredCard =
	| { kind: 'country-card'; payload: CountryCardPayload }
	| { kind: 'city-card'; payload: CityCardPayload }
	| { kind: 'nearest-card'; payload: NearestCardPayload }
	| { kind: 'intruder-card'; payload: IntruderCardPayload }
	| { kind: 'local-card'; payload: LocalCardPayload };

// One "top X% most cited in <subfield>" standing, computed server-side at
// serve time from the live peers profile + rank ladder with the same
// peers-utils machinery the entity hero uses — never stored on the card, so
// standings stay current with the dataset. Country cards only.
export type CardBadge = {
	label: string;
	subfield: string;
};

// One tappable option: `key` is what the pick compares against the answer
// (an ISO code, a city, or an institution's sem-id), `label` what it shows
// (a country card shows the flag + name of its code). Nearest cards carry
// each option's distance and place for the reveal.
export type PlayOption = LatLon & {
	key: string;
	label: string;
	km?: number;
};

// What the routes serve to the browser — one shape for every kind, the kind
// itself deciding how the prompt and the options read; `cc`/`city` place the
// anchor for the reveal. The client checks the pick locally: the per-question
// timer is what keeps lookups out.
export type PlayCard = LatLon & {
	kind: CardKind;
	semId: string;
	name: string;
	cc: string;
	city: string;
	prompt: string;
	options: PlayOption[];
	answer: string;
	note: string;
	badges: CardBadge[];
};

// `score` counts half-points (a lifelined hit is one, a plain hit two);
// `outOf` is the deck size the run drew from. The id lists are anchor sem-ids:
// difficulty signal per card, and what the share grid is drawn from.
export type RunLog = {
	mode: 'daily' | 'survival';
	day: string;
	score: number;
	outOf: number;
	missedSemIds: string[];
	lifelinedSemIds: string[];
};

// Where a daily run sits among that day's logged runs: rank 1 = nobody scored
// higher (ties share a rank). Survival runs have no standing.
export type DayStanding = {
	rank: number;
	players: number;
};

// The run POST's answer.
export type RunResult = {
	standing: DayStanding | null;
};

// One finished daily run as the browser remembers it (localStorage): the
// history behind the stats sheet and the result screen's miss recap.
export type DailyRun = Omit<RunLog, 'mode'>;

export type RunStats = {
	played: number;
	best: number;
	avg: number;
	hist: number[];
};
