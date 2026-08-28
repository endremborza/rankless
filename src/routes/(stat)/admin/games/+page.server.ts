import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import { isAdmin } from '$lib/server/admin';
import { getDb } from '$lib/server/db';
import { servedCountryPack } from '$lib/server/game-countries';
import { currentObjects } from '$lib/server/objects';

// Result tables are created lazily on the first run POST, so a fresh box
// legitimately has none — that reads as zero runs, not an error.
function countRows(table: string): number {
	const d = getDb();
	const t = d
		.prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?")
		.get(table);
	if (!t) return 0;
	return (d.prepare(`SELECT count(*) AS n FROM ${table}`).get() as { n: number }).n;
}

export const load: PageServerLoad = async ({ locals }) => {
	// 404 (not 403) so the page's existence stays hidden from non-admins.
	if (!isAdmin(locals.user?.orcid)) error(404, 'Not found');
	const clues = currentObjects('game-card').length;
	return {
		games: [
			{
				title: 'Place the Name',
				route: '/game-countries',
				kind: 'country-card',
				packCurrent: currentObjects('country-card').length,
				// served = current AND badge-gated
				packServed: (await servedCountryPack()).length,
				runs: countRows('country_game_results'),
				review: '/admin/games/countries'
			},
			{
				title: 'Guess the institution',
				route: '/game-clues',
				kind: 'game-card',
				packCurrent: clues,
				packServed: clues,
				runs: countRows('game_results'),
				review: '/mcp'
			}
		]
	};
};
