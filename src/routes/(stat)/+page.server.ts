import type { PageServerLoad } from './$types';
import { BE_URL } from '$lib/constants';
import type { TopsResponse } from '$lib/tree-types';
import { loadSpecs } from '$lib/loading-functions';

export const load: PageServerLoad = async () => {

	const treeSpecs = await loadSpecs();

	const tops: TopsResponse = await fetch(`${BE_URL}/tops`)
		.then((res) => res.json())
		.then((c) => c);

	return { tops, treeSpecs };
};

export const ssr = true;
