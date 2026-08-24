import type { PageServerLoad } from './$types';
import { currentPack, dailyCard } from '$lib/server/game';
import { utcDayStamp } from '$lib/utils/game';

// Only today's card ships with the page; practice cards load on demand via
// GET /api/game when the player triggers them.
export const load: PageServerLoad = () => {
	const day = utcDayStamp();
	return { day, card: dailyCard(day), packSize: currentPack().length };
};
