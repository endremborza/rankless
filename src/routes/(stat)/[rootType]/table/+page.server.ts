import { error } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';
import type { LadderData, MetricDecl, MetricRegistry, RootType, TableRow } from '$lib/tree-types';
import { BE_URL, COHORT_ROOT_TYPES } from '$lib/constants';
import {
	DEFAULT_SORT,
	fieldFilterable,
	sliceList,
	sliceUrl,
	TABLE_PAGE_SIZE,
	validSort
} from '$lib/table-utils';

export const ssr = true;

export const load: PageServerLoad = async ({ params, url, fetch }) => {
	const rootType = params.rootType as RootType;
	if (!COHORT_ROOT_TYPES.includes(rootType)) {
		error(404, 'Not found');
	}
	const registry: MetricDecl[] = await fetch(`${BE_URL}/metrics`)
		.then((r) => (r.ok ? (r.json() as Promise<MetricRegistry>) : { metrics: [] }))
		.then((m) => m.metrics)
		.catch(() => []);

	// A field narrows the cohort only where the registry declares the field score global.
	const subfield = fieldFilterable(registry, rootType)
		? (url.searchParams.get('subfield') ?? '')
		: '';
	const q = url.searchParams.get('q') ?? '';
	const sort = validSort(
		registry,
		rootType,
		url.searchParams.get('sort') ?? DEFAULT_SORT,
		subfield
	);
	const from = Math.max(0, parseInt(url.searchParams.get('from') ?? '0') || 0);

	let total = 0;
	const rows: TableRow[] = await fetch(sliceUrl(BE_URL, rootType, from, { sort, subfield, q }))
		.then((r) => {
			total = parseInt(r.headers.get('x-cohort-total') ?? '0') || 0;
			return r.ok ? r.json() : [];
		})
		.catch(() => []);

	// Every root type gets the subfield list: the cohort filter for the ones a field narrows, the
	// parameter of an author's page-local field column otherwise.
	const [subfields, ladder] = await Promise.all([
		sliceList(BE_URL, 'subfields', 400, fetch),
		subfield
			? fetch(`${BE_URL}/ladder/${rootType}`)
					.then((r) => (r.ok ? (r.json() as Promise<LadderData>) : null))
					.catch(() => null)
			: Promise.resolve(null)
	]);

	return {
		rootType,
		rows,
		from,
		total,
		pageSize: TABLE_PAGE_SIZE,
		sort,
		subfield,
		q,
		registry,
		subfields,
		ladder
	};
};
