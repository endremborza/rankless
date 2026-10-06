import type { Arg, Clause, Expr, Op } from './wire/rankless_expr';
import type {
	ColumnDecl,
	ColumnRegistry,
	MetricValuesResp,
	RootRegistry,
	SliceMeta,
	SliceResp,
	TableRow
} from './wire/rankless_server/responses';
import type { Kind } from './wire/rankless_trees/metrics';
import type { NamedEntity, RootType } from './tree-types';

export const TABLE_PAGE_SIZE = 100;

// The root type whose entities a metric's parameter names.
const PARAM_ROOT = { subfield: 'subfields', country: 'countries' } as const;
const PARAM_LIST_SIZE = 400;

export type MetricArgs = Arg[];

export type EntityParam = keyof typeof PARAM_ROOT;

// Display names of the entities an argument or operand points at, by semantic id.
export type Names = Record<string, string>;

// One metric call as a column: the key its values are read under, its metric and arguments.
export type Column = { key: string; decl: ColumnDecl; args: MetricArgs };

// The page's query, one key per `/slice` parameter: the ranking call, the `where` expression,
// the pins and the page offset.
export type TableQuery = { sort?: string; where?: string; pin?: string[]; from?: number };

export type MetricValues = Record<number, number | null>;

// A `/slice` page as the client holds it: the response shape plus the backend's objection if any.
export type Slice = SliceResp & { error: string | null };

export const EMPTY_REGISTRY: RootRegistry = { defaultSort: 'citations', metrics: [] };

export const EMPTY_META: SliceMeta = { total: 0, screened: null, columns: [] };
export const EMPTY_SLICE: Slice = { rows: [], meta: EMPTY_META, error: null };

// One clause of a flat `where` conjunction, as the chips show it.
export type Chip = { call: string; op: Op; operand: Arg | Arg[] };

const OP_TEXT: Record<Op, string> = {
	eq: '=',
	ne: '!=',
	lt: '<',
	le: '<=',
	gt: '>',
	ge: '>=',
	in: 'in',
	not_in: 'not in'
};

const OP_LABEL: Record<Op, string> = {
	eq: '=',
	ne: '≠',
	lt: '<',
	le: '≤',
	gt: '>',
	ge: '≥',
	in: 'in',
	not_in: 'not in'
};

export const NUMERIC_OPS: Op[] = ['ge', 'le', 'gt', 'lt', 'eq', 'ne'];
export const ENTITY_OPS: Op[] = ['eq', 'ne'];

export function metricsFor(registry: ColumnDecl[], kind: Kind) {
	return registry.filter((m) => m.kind === kind);
}

export function isNumeric(m: ColumnDecl) {
	return m.value.type !== 'entity' && m.value.type !== 'entities';
}

// Metrics that may rank the cohort: every numeric column-read metric of the root; a per-entity
// one ranks the top 1000 by citations.
export function rankable(registry: ColumnDecl[]) {
	return registry.filter((m) => isNumeric(m) && m.cost === 'read');
}

// Metrics the column adder offers: whatever the cohort's rows do not carry by themselves — every
// parameterized or per-entity metric, and the tree walks.
export function annotatable(registry: ColumnDecl[]) {
	return registry.filter(
		(m) => isNumeric(m) && (m.param !== undefined || m.kind === 'intricate' || m.cost === 'walk')
	);
}

// Metrics a clause may test: every column read of the root.
export function clauseable(registry: ColumnDecl[]) {
	return registry.filter((m) => m.cost === 'read');
}

export function operatorsFor(m: ColumnDecl) {
	return isNumeric(m) ? NUMERIC_OPS : ENTITY_OPS;
}

export function opLabel(op: Op) {
	return OP_LABEL[op];
}

function bare(s: string) {
	return (
		/^[A-Za-z_][A-Za-z0-9_-]*$/.test(s) && !['and', 'or', 'not', 'in'].includes(s.toLowerCase())
	);
}

export function argText(a: Arg) {
	if (typeof a === 'number') return String(a);
	return bare(a) ? a : `"${a.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;
}

// The canonical call text, the key of the column it makes: `papers`, `field_score(oncology)`,
// `window_papers(2020, 2024)`. Matches the backend's own spelling.
export function callText(metricId: string, args: MetricArgs) {
	return args.length ? `${metricId}(${args.map(argText).join(', ')})` : metricId;
}

// A call text back into its metric id and arguments; a quoted argument keeps its spaces.
export function parseCall(key: string): { metric: string; args: MetricArgs } {
	const m = key.match(/^([A-Za-z_][A-Za-z0-9_]*)(?:\((.*)\))?$/);
	if (!m) return { metric: key, args: [] };
	const args: MetricArgs = [];
	for (const raw of m[2] ? m[2].split(',') : []) {
		const t = raw.trim();
		if (/^"(.*)"$/.test(t)) args.push(t.slice(1, -1).replace(/\\(.)/g, '$1'));
		else if (t !== '' && !Number.isNaN(Number(t))) args.push(Number(t));
		else if (t !== '') args.push(t);
	}
	return { metric: m[1], args };
}

// A call as a column of the root, null when its registry has no such metric.
export function columnOf(key: string, registry: ColumnDecl[]): Column | null {
	const { metric, args } = parseCall(key);
	const decl = registry.find((m) => m.id === metric);
	return decl ? { key, decl, args } : null;
}

// The column the cohort is ranked by. The backend keys it by its own spelling of the call
// (`field_score(Oncology)` is `field_score(oncology)`) and lists it before any column the filter
// adds, so the first listed column of the ordering's metric is it.
export function sortColumn(columns: string[], sort: string, registry: ColumnDecl[]): Column | null {
	const typed = columnOf(sort, registry);
	const key = typed && columns.find((k) => parseCall(k).metric === typed.decl.id);
	return key ? columnOf(key, registry) : typed;
}

export function clauseText(c: Chip) {
	const operand = Array.isArray(c.operand)
		? `(${c.operand.map(argText).join(', ')})`
		: argText(c.operand);
	return `${c.call} ${OP_TEXT[c.op]} ${operand}`;
}

export function whereText(chips: Chip[]) {
	return chips.map(clauseText).join(' and ');
}

// The chips of a flat conjunction of clauses; null for any other shape, which the page shows as
// text.
export function chipsFrom(expr: Expr | null): Chip[] | null {
	if (!expr) return [];
	const items = 'and' in expr ? expr.and : [expr];
	const chips: Chip[] = [];
	for (const e of items) {
		if (!('clause' in e)) return null;
		const c: Clause = e.clause;
		chips.push({ call: callText(c.call.metric, c.call.args), op: c.op, operand: c.operand });
	}
	return chips;
}

// The column name: the header template with the argument's name (or the raw argument), or the
// label for a parameter-free metric.
export function columnLabel(decl: ColumnDecl, args: MetricArgs = [], names: Names = {}) {
	if (!decl.header) return decl.label;
	const name = (a: Arg | undefined) => (a === undefined ? '' : (names[String(a)] ?? String(a)));
	return decl.header.replace(/\{(\w+)\}/g, (_, p: string) =>
		p === 'window' ? `${name(args[0])}–${name(args[1])}` : name(args[0])
	);
}

// "Papers ≥ 100", "Country = Hungary", "Oncology citations > 0".
export function chipLabel(chip: Chip, registry: ColumnDecl[], names: Names = {}) {
	const { metric, args } = parseCall(chip.call);
	const decl = registry.find((m) => m.id === metric);
	const subject = decl ? columnLabel(decl, args, names) : chip.call;
	const shown = (a: Arg) => (typeof a === 'number' ? a.toLocaleString() : (names[a] ?? a));
	const operand = Array.isArray(chip.operand)
		? `(${chip.operand.map(shown).join(', ')})`
		: shown(chip.operand);
	return `${subject} ${OP_LABEL[chip.op]} ${operand}`;
}

export function isSet(v: string | number | null | undefined): v is string | number {
	return v != null && v !== '';
}

// The arguments a metric's parameter takes.
export function arity(decl: ColumnDecl): number {
	return decl.param === 'window' ? 2 : decl.param ? 1 : 0;
}

// A call's arguments are all given; what they say is the backend's to check.
export function argsReady(decl: ColumnDecl, args: MetricArgs): boolean {
	return args.length === arity(decl) && args.every(isSet);
}

// The arguments a metric starts with: `base` where it fits the parameter, else the last five years
// with yearly counts for a window, else nothing chosen yet.
export function defaultArgs(
	decl: ColumnDecl,
	base: MetricArgs,
	yearly?: [number, number]
): MetricArgs {
	if (base.length === arity(decl)) return base;
	if (decl.param === 'window' && yearly) return [Math.max(yearly[0], yearly[1] - 5), yearly[1]];
	return [];
}

export function byName<T extends { name: string }>(list: T[]): T[] {
	return [...list].sort((a, b) => a.name.localeCompare(b.name));
}

export function namesOf(list: NamedEntity[]): Names {
	return Object.fromEntries(list.map((e) => [e.semanticId, e.name]));
}

export function rowValue(row: TableRow, key: string): number | undefined {
	return row.values[key];
}

export function rankText(row: TableRow): string {
	return row.rank?.toLocaleString() ?? '–';
}

// How many entities a per-entity ordering ranked, the most cited ones; null when it ranked all.
export function screenedTop(meta: Pick<SliceMeta, 'total' | 'screened'>): number | null {
	return meta.screened !== null && meta.screened < meta.total ? meta.screened : null;
}

export function screenedPhrase(top: number): string {
	return `among the top ${top.toLocaleString()} by citations`;
}

export function formatMetric(decl: ColumnDecl | undefined, v: number | null | undefined): string {
	if (v == null) return '–';
	switch (decl?.value.type) {
		case 'score':
			return v >= 100 ? Math.round(v).toLocaleString() : v.toFixed(v >= 10 ? 1 : 2);
		case 'year':
			return v.toFixed(1);
		case 'share': {
			const pct = v * 100;
			return `${pct.toFixed(pct >= 1 ? 1 : 2)}%`;
		}
		default:
			return Math.round(v).toLocaleString();
	}
}

// Stable sort with missing values last, for the page-local ordering of a column.
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

// `defaultSort` is left out of a page link, which the root's default restores; a slice request
// always names its sort.
function queryString(q: TableQuery, defaultSort?: string) {
	const p = new URLSearchParams();
	if (q.sort && q.sort !== defaultSort) p.set('sort', q.sort);
	if (q.where) p.set('where', q.where);
	if (q.pin?.length) p.set('pin', q.pin.join(','));
	if (q.from) p.set('from', String(q.from));
	const qs = p.toString();
	return qs ? `?${qs}` : '';
}

export function tableHref(rootType: RootType, q: TableQuery, defaultSort?: string) {
	return `/${rootType}/table${queryString(q, defaultSort)}`;
}

// The ranking call and the `where` expression a table URL names, as typed: the backend is the one
// parser, and its objection is the caller's to show. A URL naming no ordering gets the root's.
export function tableQuery(sp: URLSearchParams, defaultSort: string): TableQuery {
	return { sort: sp.get('sort') || defaultSort, where: sp.get('where') ?? '' };
}

export function sliceUrl(base: string, rootType: RootType, from: number, q: TableQuery) {
	const qs = queryString({ ...q, from: undefined });
	return `${base}/slice/${rootType}/${from}/${from + TABLE_PAGE_SIZE}${qs}`;
}

// One page of the cohort in the active ordering and the meta it is read against; with `pin`, the
// pinned entities' rows instead. A rejected query yields its message.
export function fetchSlice(
	base: string,
	rootType: RootType,
	from: number,
	q: TableQuery,
	fetchFn: typeof fetch = fetch
): Promise<Slice> {
	return fetchFn(sliceUrl(base, rootType, from, q))
		.then(async (r) => {
			if (!r.ok) return { ...EMPTY_SLICE, error: (await r.text()) || r.statusText };
			return { ...((await r.json()) as SliceResp), error: null };
		})
		.catch(() => EMPTY_SLICE);
}

// The cohort's page at `from` and the rows of the pinned entities, both in the query's ordering.
export async function fetchCohort(
	base: string,
	rootType: RootType,
	{ pin = [], from = 0, ...query }: TableQuery,
	fetchFn: typeof fetch = fetch
): Promise<{ page: Slice; pinned: Slice }> {
	const [page, pinned] = await Promise.all([
		fetchSlice(base, rootType, from, query, fetchFn),
		pin.length ? fetchSlice(base, rootType, 0, { ...query, pin }, fetchFn) : EMPTY_SLICE
	]);
	return { page, pinned };
}

// The root's metrics and default ordering, null when the backend does not serve them.
export function fetchRegistry(
	base: string,
	rootType: RootType,
	fetchFn: typeof fetch = fetch
): Promise<RootRegistry | null> {
	return fetchFn(`${base}/columns`)
		.then((r) => (r.ok ? (r.json() as Promise<ColumnRegistry>) : null))
		.then((reg) => reg?.roots[rootType] ?? null)
		.catch(() => null);
}

// The backend's parse of a `where` expression, null when it is empty or refused.
export function fetchWhere(
	base: string,
	where: string,
	fetchFn: typeof fetch = fetch
): Promise<Expr | null> {
	if (!where.trim()) return Promise.resolve(null);
	return fetchFn(`${base}/where?${new URLSearchParams({ q: where })}`)
		.then((r) => (r.ok ? (r.json() as Promise<Expr>) : null))
		.catch(() => null);
}

// Every field or country a metric's argument may name, in the type's default ordering.
export function fetchParamEntities(
	base: string,
	param: EntityParam,
	fetchFn: typeof fetch = fetch
): Promise<NamedEntity[]> {
	return fetchFn(`${base}/slice/${PARAM_ROOT[param]}/0/${PARAM_LIST_SIZE}`)
		.then((r) => (r.ok ? (r.json() as Promise<SliceResp>) : EMPTY_SLICE))
		.then((s) => s.rows)
		.catch(() => []);
}

// One call for a page: every id on screen and the column's metric call.
export function metricValuesUrl(base: string, rootType: RootType, ids: number[], call: string) {
	const p = new URLSearchParams({ ids: ids.join(','), metrics: call });
	return `${base}/metrics/${rootType}?${p.toString()}`;
}

// One column's values for a page of rows, keyed by dm id, with the backend's objection if any. The
// backend answers under its own spelling of the call: the one column it returns is the answer, and
// `key` is that spelling.
export async function fetchColumnValues(
	base: string,
	rootType: RootType,
	rows: TableRow[],
	col: Column,
	fetchFn: typeof fetch = fetch
): Promise<{ key: string; values: MetricValues; error: string | null }> {
	const ids = rows.map((r) => r.dmId);
	const values: MetricValues = {};
	const r = await fetchFn(metricValuesUrl(base, rootType, ids, col.key)).catch(() => null);
	if (!r) return { key: col.key, values, error: 'unreachable' };
	if (!r.ok) return { key: col.key, values, error: (await r.text()) || r.statusText };
	const resp = (await r.json()) as MetricValuesResp;
	const [[key, column] = [col.key, undefined]] = Object.entries(resp.values);
	resp.ids.forEach((id, i) => (values[id] = column?.[i] ?? null));
	return { key, values, error: null };
}
