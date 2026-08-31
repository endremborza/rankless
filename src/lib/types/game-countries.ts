// Country-game card shapes. Source of truth: pyscripts/explore/country_cards.py
// writes `country-card` objects into the MCP object store — institutions whose
// names mislead about their country, with three LLM-picked decoy countries.

export type CountryCard = {
	semId: string;
	name: string;
	cc: string;
	decoys: string[];
	note: string;
	papers: number;
	citations: number;
};

// One "top X% most cited in <subfield>" standing, computed server-side at
// serve time from the live peers profile + rank ladder with the same
// peers-utils machinery the entity hero uses — never stored on the card, so
// standings stay current with the dataset.
export type CountryBadge = {
	label: string;
	subfield: string;
};

// A stored card enriched with its live standings — what the served pack holds
// (a card without any badge never serves).
export type BadgedCountryCard = CountryCard & { badges: CountryBadge[] };

// What the routes serve to the browser: correct country folded into a shuffled
// `options` list (the client checks the pick locally, like the clue game ships
// its target coordinates).
export type CountryPlayCard = Omit<BadgedCountryCard, 'decoys' | 'papers' | 'citations'> & {
	options: string[];
};

// `outOf` is the deck size the run drew from, so a sweep (score + misses ===
// outOf) and the lives left (LIVES - misses) both stay derivable without
// storing either.
export type CountryRunLog = {
	mode: 'daily' | 'practice';
	day: string;
	score: number;
	outOf: number;
	missedSemIds: string[];
};

// Where a daily run sits among that day's logged runs: rank 1 = nobody scored
// higher (ties share a rank). Practice runs have no standing.
export type DayStanding = {
	rank: number;
	players: number;
};

// The run POST's answer.
export type CountryRunResult = {
	standing: DayStanding | null;
};

// One finished daily run as the browser remembers it (localStorage): the
// history behind the stats sheet and the result screen's miss recap.
export type DailyRun = {
	day: string;
	score: number;
	outOf: number;
	missedIds: string[];
};

export type RunStats = {
	played: number;
	best: number;
	avg: number;
	hist: number[];
};
