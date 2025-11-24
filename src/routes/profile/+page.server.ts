import { BE_URL } from '$lib/constants';
import type { SearchResult } from '$lib/tree-types';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals }) => {
	if (!locals.user) {
		// return {}
		// throw new Response('Unauthorized', { status: 302, headers: { Location: '/' } });
	}
	let user = locals.user;
	// cesar
	// 0000-0002-6977-9492
	// baker
	// 0000-0001-7896-6217
	// hassibis
	// 0000-0003-2812-9917
	user = { name: 'Test Name', orcid: '0000-0001-5196-5599' }
	let orcidId = user.orcid;
	let searchResult: SearchResult = await fetch(
		`${BE_URL}/orcid/${orcidId}`)
		.then((res) => res.json());
	return { user, searchResult };
};
