import type { PageServerLoad } from './$types';
import { BE_URL } from '$lib/constants';
import type { RootType, SearchResult } from '$lib/tree-types';

export const load: PageServerLoad = async () => {
	const tops: { name: RootType; entities: SearchResult[] }[] = await fetch(`${BE_URL}/tops`)
		.then((res) => res.json())
		.then((c) => c);
	return { tops };
};

export const ssr = true;
