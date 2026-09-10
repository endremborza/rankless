import type { PageServerLoad } from './$types';
import { servedDailyDeck } from '$lib/server/game-geo';
import { utcDayStamp } from '$lib/utils/game';

// The whole daily deck ships with the page: the run is timed, so the player
// never has a lookup window anyway, and survival decks load on demand via
// GET /api/game-geo.
export const load: PageServerLoad = async () => {
	const day = utcDayStamp();
	return { day, deck: await servedDailyDeck(day) };
};
