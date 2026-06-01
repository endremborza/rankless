import type { PageServerLoad } from './$types';
import { getTopTreeLoader } from '$lib/loading-functions';

export const load: PageServerLoad = async ({ fetch }) => {
	let loader = await getTopTreeLoader(fetch);
	while (loader.conf == undefined) {
		await loader.setRandTree(fetch);
	}
	return { ...loader };
};

export const ssr = true;
