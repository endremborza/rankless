import type {
	MetricDecl,
	MetricKind,
	MetricValuesResp,
	RootType,
	SearchResult,
	TableRow,
	WhereArg,
	WhereClause,
	WhereExpr,
	WhereOp
} from './tree-types';

export const TABLE_PAGE_SIZE = 100;
export const DEFAULT_SORT = 'citations';

export type MetricArgs = WhereArg[];

// Display names of the entities an argument or operand points at, by semantic id.
export type Names = Record<string, string>;

// One page-local column: a metric call and the label it was added under.
export type Column = { key: string; label: string; metric: MetricDecl; args: MetricArgs };

// The page's query, one key per `/slice` parameter: the ranking call, the `where` expression,
// the pins and the page offset.
export type TableQuery = { sort?: string; where?: string; pin?: string[]; from?: number };

export type MetricValues = Record<number, number | null>;

// A page of rows, the size of the cohort they are ranked in, for a screened ranking the size of
// the ranked set, the metric columns the rows carry, and the backend's objection if any.
export type Slice = {
	rows: TableRow[];
	total: number;
	screened: number | null;
	columns: string[];
	error: string | null;
};

// One clause of a flat `where` conjunction, as the chips show it.
export type Chip = { call: string; op: WhereOp; operand: WhereArg | WhereArg[] };

const OP_TEXT: Record<WhereOp, string> = {
	eq: '=',
	ne: '!=',
	lt: '<',
	le: '<=',
	gt: '>',
	ge: '>=',
	in: 'in',
	not_in: 'not in'
};

const OP_LABEL: Record<WhereOp, string> = {
	eq: '=',
	ne: '≠',
	lt: '<',
	le: '≤',
	gt: '>',
	ge: '≥',
	in: 'in',
	not_in: 'not in'
};

export const NUMERIC_OPS: WhereOp[] = ['ge', 'le', 'gt', 'lt', 'eq', 'ne'];
export const ENTITY_OPS: WhereOp[] = ['eq', 'ne'];

export function metricsFor(registry: MetricDecl[], rootType: RootType, kind: MetricKind) {
	return registry.filter((m) => m.kinds[rootType] === kind);
}

export function isNumeric(m: MetricDecl) {
	return m.value.type !== 'entity' && m.value.type !== 'entities';
}

// Metrics that may rank the cohort: every numeric column-read metric of the root; a per-entity
// one ranks the top 1000 by citations.
export function rankable(registry: MetricDecl[], rootType: RootType) {
	return registry.filter((m) => m.kinds[rootType] && isNumeric(m) && m.cost === 'read');
}

// Metrics the column adder offers: whatever the cohort's rows do not carry by themselves — every
// parameterized or per-entity metric, and the tree walks.
export function annotatable(registry: MetricDecl[], rootType: RootType) {
	return registry.filter(
		(m) =>
			m.kinds[rootType] &&
			isNumeric(m) &&
			(m.param !== undefined || m.kinds[rootType] === 'intricate' || m.cost === 'walk')
	);
}

// Metrics a clause may test: every column read of the root.
export function clauseable(registry: MetricDecl[], rootType: RootType) {
	return registry.filter((m) => m.kinds[rootType] && m.cost === 'read');
}

export function operatorsFor(m: MetricDecl) {
	return isNumeric(m) ? NUMERIC_OPS : ENTITY_OPS;
}

export function opLabel(op: WhereOp) {
	return OP_LABEL[op];
}

function bare(s: string) {
	return (
		/^[A-Za-z_][A-Za-z0-9_-]*$/.test(s) && !['and', 'or', 'not', 'in'].includes(s.toLowerCase())
	);
}

export function argText(a: WhereArg) {
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
export function chipsFrom(expr: WhereExpr | null): Chip[] | null {
	if (!expr) return [];
	const items = 'and' in expr ? expr.and : [expr];
	const chips: Chip[] = [];
	for (const e of items) {
		if (!('clause' in e)) return null;
		const c: WhereClause = e.clause;
		chips.push({ call: callText(c.call.metric, c.call.args), op: c.op, operand: c.operand });
	}
	return chips;
}

// The column name: the header template with the argument's name (or the raw argument), or the
// label for a parameter-free metric.
export function columnLabel(decl: MetricDecl, args: MetricArgs = [], names: Names = {}) {
	if (!decl.header) return decl.label;
	const name = (a: WhereArg | undefined) =>
		a === undefined ? '' : (names[String(a)] ?? String(a));
	return decl.header.replace(/\{(\w+)\}/g, (_, p: string) =>
		p === 'window' ? `${name(args[0])}–${name(args[1])}` : name(args[0])
	);
}

// "Papers ≥ 100", "Country = Hungary", "Oncology citations > 0".
export function chipLabel(chip: Chip, registry: MetricDecl[], names: Names = {}) {
	const { metric, args } = parseCall(chip.call);
	const decl = registry.find((m) => m.id === metric);
	const subject = decl ? columnLabel(decl, args, names) : chip.call;
	const shown = (a: WhereArg) => (typeof a === 'number' ? a.toLocaleString() : (names[a] ?? a));
	const operand = Array.isArray(chip.operand)
		? `(${chip.operand.map(shown).join(', ')})`
		: shown(chip.operand);
	return `${subject} ${OP_LABEL[chip.op]} ${operand}`;
}

export function isSet(v: string | number | null | undefined): v is string | number {
	return v != null && v !== '';
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

export function formatMetric(decl: MetricDecl | undefined, v: number | null | undefined): string {
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

function queryString(q: TableQuery, withDefaults: boolean) {
	const p = new URLSearchParams();
	if (q.sort && (withDefaults || q.sort !== DEFAULT_SORT)) p.set('sort', q.sort);
	if (q.where) p.set('where', q.where);
	if (q.pin?.length) p.set('pin', q.pin.join(','));
	if (q.from) p.set('from', String(q.from));
	const qs = p.toString();
	return qs ? `?${qs}` : '';
}

export function tableHref(rootType: RootType, q: TableQuery) {
	return `/${rootType}/table${queryString(q, false)}`;
}

export function sliceUrl(base: string, rootType: RootType, from: number, q: TableQuery) {
	const qs = queryString({ ...q, from: undefined }, true);
	return `${base}/slice/${rootType}/${from}/${from + TABLE_PAGE_SIZE}${qs}`;
}

// One page of the cohort in the active ordering, the cohort's size and the columns its rows
// carry; with `pin`, the pinned entities' rows instead. A rejected query yields its message.
export function fetchSlice(
	base: string,
	rootType: RootType,
	from: number,
	q: TableQuery,
	fetchFn: typeof fetch = fetch
): Promise<Slice> {
	const count = (h: string | null) => parseInt(h ?? '0') || 0;
	const none: Slice = { rows: [], total: 0, screened: null, columns: [], error: null };
	return fetchFn(sliceUrl(base, rootType, from, q))
		.then(async (r) => {
			if (!r.ok) return { ...none, error: (await r.text()) || r.statusText };
			return {
				rows: (await r.json()) as TableRow[],
				total: count(r.headers.get('x-cohort-total')),
				screened: r.headers.has('x-screened-k') ? count(r.headers.get('x-screened-k')) : null,
				columns: (r.headers.get('x-columns') ?? '').split(',').filter(Boolean),
				error: null
			};
		})
		.catch(() => none);
}

// The backend's parse of a `where` expression, null when it is empty or refused.
export function fetchWhere(
	base: string,
	where: string,
	fetchFn: typeof fetch = fetch
): Promise<WhereExpr | null> {
	if (!where.trim()) return Promise.resolve(null);
	return fetchFn(`${base}/where?${new URLSearchParams({ q: where })}`)
		.then((r) => (r.ok ? (r.json() as Promise<WhereExpr>) : null))
		.catch(() => null);
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

// One call for a page: every id on screen and the column's metric call.
export function metricValuesUrl(base: string, rootType: RootType, ids: number[], call: string) {
	const p = new URLSearchParams({ ids: ids.join(','), metrics: call });
	return `${base}/metrics/${rootType}?${p.toString()}`;
}

// A column's values for the given rows, keyed by dm id; a row the server did not answer is absent.
export async function fetchColumnValues(
	base: string,
	rootType: RootType,
	rows: TableRow[],
	col: Column
): Promise<MetricValues> {
	const ids = rows.map((r) => r.dmId);
	const resp: MetricValuesResp | null = await fetch(metricValuesUrl(base, rootType, ids, col.key))
		.then((r) => (r.ok ? r.json() : null))
		.catch(() => null);
	const got: MetricValues = {};
	const column = resp?.values[col.key] ?? Object.values(resp?.values ?? {})[0];
	resp?.ids.forEach((id, i) => (got[id] = column?.[i] ?? null));
	return got;
}
