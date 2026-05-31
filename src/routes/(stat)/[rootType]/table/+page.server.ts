import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import type { SearchResult, RootType } from '$lib/tree-types';
import { BE_URL, ROOT_TYPES } from '$lib/constants';

const PAGE_SIZE = 100;

export const ssr = true;

export const load: PageServerLoad = async ({ params, url }) => {
	const rootType = params.rootType as RootType;
	if (!ROOT_TYPES.includes(rootType) || rootType === 'hit-papers') {
		error(404, 'Not found');
	}

	const from = Math.max(0, parseInt(url.searchParams.get('from') ?? '0'));

	const rows: SearchResult[] = await fetch(
		`${BE_URL}/slice/${rootType}/${from}/${from + PAGE_SIZE}`
	)
		.then((r) => (r.ok ? r.json() : []))
		.catch(() => []);

	const hasMore = rows.length === PAGE_SIZE;

	return { rootType, rows, from, hasMore, pageSize: PAGE_SIZE };
};
