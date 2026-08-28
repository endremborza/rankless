import type { PageServerLoad } from './$types';
import { newDeck } from '$lib/server/game-countries';
import { utcDayStamp } from '$lib/utils/game';

// A whole (capped) freshly shuffled deck ships with the page: the run is
// timed, so the player never has a lookup window anyway, and practice decks
// load on demand via GET /api/game-countries.
export const load: PageServerLoad = () => {
	return { day: utcDayStamp(), deck: newDeck() };
};
