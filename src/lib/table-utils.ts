import type { MetricDecl, MetricKind, RootType, SearchResult, TableRow } from './tree-types';

export const TABLE_PAGE_SIZE = 100;
export const DEFAULT_SORT = 'citations';

// A number input bound with bind:value reads null once cleared.
export type MetricParams = {
	subfield?: string;
	year_from?: number | null;
	year_to?: number | null;
	country?: string;
};

// One page-local column: an intricate metric bound to the parameters it was added with. Two
// windows of the same metric are two columns, so the key carries the parameters.
export type IntricateColumn = { key: string; metric: MetricDecl; params: MetricParams };

export type TableQuery = { sort?: string; subfield?: string; q?: string; from?: number };

const ROW_FIELD: Record<string, keyof TableRow> = {
	papers: 'papers',
	citations: 'citations',
	impact_score: 'impactScore',
	h_index: 'hIndex',
	year_centroid: 'yearCentroid',
	field_citations: 'fieldCitations',
	field_score: 'fieldScore'
};

export function metricsFor(registry: MetricDecl[], rootType: RootType, kind: MetricKind) {
	return registry.filter((m) => m.kinds[rootType] === kind);
}

// Global columns of the table: the field ones only once the cohort is narrowed to a subfield.
export function globalColumns(registry: MetricDecl[], rootType: RootType, hasField: boolean) {
	return metricsFor(registry, rootType, 'global').filter(
		(m) => hasField || !m.params.includes('subfield')
	);
}

// The cohort can be narrowed to a field only where the registry declares the field score global.
export function fieldFilterable(registry: MetricDecl[], rootType: RootType) {
	return registry.some((m) => m.id === 'field_score' && m.kinds[rootType] === 'global');
}

// A sort the server can serve for this root type; anything else falls back to citations.
export function validSort(
	registry: MetricDecl[],
	rootType: RootType,
	sort: string,
	subfield: string
) {
	const ok = globalColumns(registry, rootType, subfield !== '').some((m) => m.id === sort);
	return ok ? sort : DEFAULT_SORT;
}

export function isSet(v: string | number | null | undefined): v is string | number {
	return v != null && v !== '';
}

export function rowValue(row: TableRow, metricId: string): number | undefined {
	const field = ROW_FIELD[metricId];
	return field ? (row[field] as number | undefined) : undefined;
}

export function formatMetric(metricId: string, v: number | null | undefined): string {
	if (v == null) return '–';
	switch (metricId) {
		case 'impact_score':
		case 'field_score':
			return v >= 100 ? Math.round(v).toLocaleString() : v.toFixed(v >= 10 ? 1 : 2);
		case 'year_centroid':
			return v.toFixed(1);
		case 'citing_country_share':
			return `${(v * 100).toFixed(1)}%`;
		default:
			return Math.round(v).toLocaleString();
	}
}

// Stable sort with missing values last, for the page-local ordering of an intricate column.
export function sortRows<T>(rows: T[], value: (r: T) => number | null | undefined, asc: boolean) {
	return rows
		.map((r, i) => ({ r, i, v: value(r) }))
		.sort((a, b) => {
			if (a.v == null && b.v == null) return a.i - b.i;
			if (a.v == null) return 1;
			if (b.v == null) return -1;
			const cmp = a.v - b.v;
			return (asc ? cmp : -cmp) || a.i - b.i;
		})
		.map((x) => x.r);
}

export function columnKey(metricId: string, params: MetricParams) {
	const parts = Object.entries(params)
		.filter(([, v]) => isSet(v))
		.sort(([a], [b]) => a.localeCompare(b))
		.map(([k, v]) => `${k}=${v}`);
	return [metricId, ...parts].join('|');
}

export function tableHref(rootType: RootType, q: TableQuery) {
	const p = new URLSearchParams();
	if (q.sort && q.sort !== DEFAULT_SORT) p.set('sort', q.sort);
	if (q.subfield) p.set('subfield', q.subfield);
	if (q.q) p.set('q', q.q);
	if (q.from) p.set('from', String(q.from));
	const qs = p.toString();
	return `/${rootType}/table${qs ? `?${qs}` : ''}`;
}

// The first `n` entities of a root type by citations, for the field and country pickers.
export function sliceList(
	base: string,
	rootType: RootType,
	n: number,
	fetchFn: typeof fetch = fetch
): Promise<SearchResult[]> {
	return fetchFn(`${base}/slice/${rootType}/0/${n}`)
		.then((r) => (r.ok ? r.json() : []))
		.catch(() => []);
}

export function sliceUrl(base: string, rootType: RootType, from: number, q: TableQuery) {
	const p = new URLSearchParams();
	if (q.sort) p.set('sort', q.sort);
	if (q.subfield) p.set('subfield', q.subfield);
	if (q.q) p.set('q', q.q);
	const qs = p.toString();
	return `${base}/slice/${rootType}/${from}/${from + TABLE_PAGE_SIZE}${qs ? `?${qs}` : ''}`;
}

// One call for a page: every id on screen, the column's metric and its parameters.
export function metricValuesUrl(
	base: string,
	rootType: RootType,
	ids: number[],
	metricId: string,
	params: MetricParams
) {
	const p = new URLSearchParams({ ids: ids.join(','), metrics: metricId });
	for (const [k, v] of Object.entries(params)) {
		if (isSet(v)) p.set(k, String(v));
	}
	return `${base}/metrics/${rootType}?${p.toString()}`;
}
