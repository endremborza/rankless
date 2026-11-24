import type { PageServerLoad } from './$types';
import { requireAdmin } from '$lib/server/admin';
import { getDb } from '$lib/server/db';
import { servedPack } from '$lib/server/game-geo';
import { currentObjects } from '$lib/server/objects';
import { KINDS, isMedicalName } from '$lib/utils/game-geo';

export const load: PageServerLoad = async ({ locals, url }) => {
	requireAdmin(locals, url);
	const served = await servedPack();
	return {
		// served = current AND (for country cards) badge-gated; medical names
		// are quota'd per daily, so their served share is shown
		kinds: KINDS.map((kind) => ({
			kind,
			current: currentObjects(kind).length,
			served: served.filter((c) => c.kind === kind).length,
			medical: served.filter((c) => c.kind === kind && isMedicalName(c.name)).length
		})),
		runs: (getDb().prepare('SELECT count(*) AS n FROM geo_game_runs').get() as { n: number }).n
	};
};
