import type { PageServerLoad } from './$types';
import { currentPack, dailyCard } from '$lib/server/game-clues';
import { utcDayStamp } from '$lib/utils/game';

// Only today's card ships with the page; practice cards load on demand via
// GET /api/game-clues when the player triggers them.
export const load: PageServerLoad = () => {
	const day = utcDayStamp();
	const pack = currentPack();
	return { day, card: dailyCard(day, pack), packSize: pack.length };
};
