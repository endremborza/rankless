import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import type { LadderData, MetricRegistry, RootType } from '$lib/tree-types';
import { BE_URL, COHORT_ROOT_TYPES } from '$lib/constants';
import {
	byName,
	chipsFrom,
	DEFAULT_SORT,
	fetchSlice,
	fetchWhere,
	parseCall,
	sliceList,
	TABLE_PAGE_SIZE,
	type Slice,
	type TableQuery
} from '$lib/table-utils';

export const ssr = true;

const EMPTY: MetricRegistry = { metrics: [] };

export const load: PageServerLoad = async ({ params, url, fetch }) => {
	const rootType = params.rootType as RootType;
	if (!COHORT_ROOT_TYPES.includes(rootType)) {
		error(404, 'Not found');
	}
	const { metrics: registry } = await fetch(`${BE_URL}/columns`)
		.then((r) => (r.ok ? (r.json() as Promise<MetricRegistry>) : EMPTY))
		.catch(() => EMPTY);
	const sp = url.searchParams;
	// The query is handed to the backend as typed: it is the one parser, and its objection is
	// shown on the page.
	const query: TableQuery = {
		sort: sp.get('sort') || DEFAULT_SORT,
		where: sp.get('where') ?? ''
	};
	const from = Math.max(0, parseInt(sp.get('from') ?? '0') || 0);
	const pin = sp.get('pin')?.split(',').filter(Boolean) ?? [];
	const none: Slice = { rows: [], total: 0, screened: null, columns: [], error: null };

	const [page, pinned, parsed, subfields, countries] = await Promise.all([
		fetchSlice(BE_URL, rootType, from, query, fetch),
		pin.length ? fetchSlice(BE_URL, rootType, 0, { ...query, pin }, fetch) : none,
		fetchWhere(BE_URL, query.where ?? '', fetch),
		sliceList(BE_URL, 'subfields', 400, fetch).then(byName),
		sliceList(BE_URL, 'countries', 400, fetch).then(byName)
	]);
	// The standing column reads the ladder of the field the cohort's columns are about.
	const fieldKey = page.columns.find((c) => c.startsWith('field_citations('));
	const field = fieldKey ? String(parseCall(fieldKey).args[0] ?? '') : '';
	const ladder = field
		? await fetch(`${BE_URL}/ladder/${rootType}`)
				.then((r) => (r.ok ? (r.json() as Promise<LadderData>) : null))
				.catch(() => null)
		: null;

	return {
		rootType,
		rows: page.rows,
		total: page.total,
		screened: page.screened,
		columns: page.columns,
		error: page.error,
		pinned: pinned.rows,
		pin,
		from,
		pageSize: TABLE_PAGE_SIZE,
		query,
		chips: query.where && !parsed ? null : chipsFrom(parsed),
		field,
		registry,
		subfields,
		countries,
		ladder
	};
};
