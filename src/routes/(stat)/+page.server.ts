import type { PageServerLoad } from './$types';
import { getTopTreeLoader } from '$lib/loading-functions';

export const load: PageServerLoad = async () => {
	let loader = await getTopTreeLoader();
	while (loader.conf == undefined) {
		await loader.setRandTree();
	}
	return { ...loader };
};

export const ssr = true;
