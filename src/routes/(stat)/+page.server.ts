import type { PageServerLoad } from './$types';
import { BE_URL } from '$lib/constants';
import type { TopsResponse } from '$lib/tree-types';

export const load: PageServerLoad = async () => {

	const treeSpecs = await fetch(`${BE_URL}/specs`)
		.then((res) => res.json())
		.then((specs) => specs);

	const tops: TopsResponse = await fetch(`${BE_URL}/tops`)
		.then((res) => res.json())
		.then((c) => c);

	return { tops, treeSpecs };
};

export const ssr = true;
