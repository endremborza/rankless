// Country-game card shapes. Source of truth: pyscripts/explore/country_cards.py
// writes `country-card` objects into the MCP object store — universities whose
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

// What the routes serve to the browser: correct country folded into a shuffled
// `options` list (the client checks the pick locally, like the clue game ships
// its target coordinates).
export type CountryPlayCard = Omit<CountryCard, 'decoys' | 'papers' | 'citations'> & {
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
