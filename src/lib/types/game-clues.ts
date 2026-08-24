// Game clue-card shapes. Source of truth: pyscripts/explore/game_cards.py
// writes `game-card` objects into the MCP object store; facts carry the
// reproduced backend calls that verified each clue.

export type GameFact = {
	tool: string;
	args: Record<string, unknown>;
	path: string;
	claimed: unknown;
	reproduced: unknown;
	error: string | null;
	ok: boolean;
};

export type GameClue = {
	stage: number;
	text: string;
	facts: GameFact[];
};

export type GameCard = {
	semId: string;
	name: string;
	cc: string;
	lat: number;
	lon: number;
	papers: number;
	citations: number;
	clues: GameClue[];
};

// What the game routes serve to the browser: the card without its verification
// facts (dead weight client-side, and the full pack never ships at once).
export type PlayClue = Pick<GameClue, 'stage' | 'text'>;
export type PlayCard = Omit<GameCard, 'clues'> & { clues: PlayClue[] };

export type GameResultLog = {
	mode: 'daily' | 'practice';
	day: string;
	semId: string;
	cluesUsed: number;
	gaveUp: boolean;
	guessLat: number | null;
	guessLon: number | null;
	distanceKm: number | null;
	score: number;
};
