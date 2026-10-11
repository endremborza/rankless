import { BE_URL } from '$lib/constants';
import type { RootType } from '$lib/tree-types';
import movedRaw from '$lib/assets/data/moved-semantic-ids.json?raw';

// Slugs a past release served, by root type, each with its entity's OpenAlex id: the id finds the
// entity's slug in the served release, however the slug rule has renamed it since.
const MOVED: Partial<Record<RootType, Record<string, number>>> = JSON.parse(movedRaw);

export async function movedSemanticId(
	rootType: RootType,
	semanticId: string,
	fetchFn: typeof fetch
): Promise<string | undefined> {
	const oaId = MOVED[rootType]?.[semanticId];
	if (oaId === undefined) return undefined;
	const [current]: [string | null] = await fetchFn(`${BE_URL}/sem-id-via-oa/${rootType}/${oaId}`)
		.then((res) => res.json())
		.catch(() => [null]);
	return current ?? undefined;
}
