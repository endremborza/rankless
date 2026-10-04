import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import type { LadderData, RootType } from '$lib/tree-types';
import { BE_URL, COHORT_ROOT_TYPES } from '$lib/constants';
import {
	byName,
	chipsFrom,
	EMPTY_REGISTRY,
	fetchCohort,
	fetchParamEntities,
	fetchRegistry,
	fetchWhere,
	parseCall,
	TABLE_PAGE_SIZE,
	tableQuery
} from '$lib/table-utils';

export const ssr = true;

export const load: PageServerLoad = async ({ params, url, fetch }) => {
	const rootType = params.rootType as RootType;
	if (!COHORT_ROOT_TYPES.includes(rootType)) {
		error(404, 'Not found');
	}
	const { defaultSort, metrics: registry } =
		(await fetchRegistry(BE_URL, rootType, fetch)) ?? EMPTY_REGISTRY;
	const sp = url.searchParams;
	const query = tableQuery(sp, defaultSort);
	const from = Math.max(0, parseInt(sp.get('from') ?? '0') || 0);
	const pin = sp.get('pin')?.split(',').filter(Boolean) ?? [];

	const [{ page, pinned }, parsed, subfields, countries] = await Promise.all([
		fetchCohort(BE_URL, rootType, { ...query, pin, from }, fetch),
		fetchWhere(BE_URL, query.where ?? '', fetch),
		fetchParamEntities(BE_URL, 'subfield', fetch).then(byName),
		fetchParamEntities(BE_URL, 'country', fetch).then(byName)
	]);
	// The standing column reads the ladder of the field the cohort's columns are about.
	const fieldKey = page.meta.columns.find((c) => c.startsWith('field_citations('));
	const field = fieldKey ? String(parseCall(fieldKey).args[0] ?? '') : '';
	const ladder = field
		? await fetch(`${BE_URL}/ladder/${rootType}`)
				.then((r) => (r.ok ? (r.json() as Promise<LadderData>) : null))
				.catch(() => null)
		: null;

	return {
		rootType,
		rows: page.rows,
		total: page.meta.total,
		screened: page.meta.screened,
		columns: page.meta.columns,
		error: page.error,
		pinned: pinned.rows,
		pin,
		from,
		pageSize: TABLE_PAGE_SIZE,
		query,
		chips: query.where && !parsed ? null : chipsFrom(parsed),
		field,
		registry,
		defaultSort,
		subfields,
		countries,
		ladder
	};
};
