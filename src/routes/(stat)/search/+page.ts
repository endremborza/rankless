import type { PageLoad } from './$types';

export const load: PageLoad = ({ url }) => {
	return { q: url.searchParams.get('q') ?? '' };
};
