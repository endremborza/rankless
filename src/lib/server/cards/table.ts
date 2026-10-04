import { error } from '@sveltejs/kit';
import type * as tt from '$lib/tree-types';
import { BE_URL } from '$lib/constants';
import { prettifyRoot } from '$lib/text-format-util';
import { htmlToText } from '$lib/utils/paper-helpers';
import {
	arity,
	columnLabel,
	columnOf,
	fetchCohort,
	fetchColumnValues,
	fetchParamEntities,
	fetchRegistry,
	formatMetric,
	isNumeric,
	namesOf,
	rankText,
	rowValue,
	screenedPhrase,
	screenedTop,
	sortColumn,
	tableQuery,
	type Column,
	type MetricValues,
	type Names
} from '$lib/table-utils';
import TableCard, {
	type TableCardColumn,
	type TableCardRow
} from '$lib/components/cards/TableCard.svelte';
import { CARD_SPEC, ID_CHARS, idsParam, intParam, type CardKind } from './kind';

const P = CARD_SPEC.table.params;
// The ranking's own column and the added ones.
const MAX_COLUMNS = 1 + P.cols.max;

// The cohort's ranking table: `sort` and `where` go to the backend as typed, `n` ranked rows from
// rank `from` + 1 on, `pin` entities (and the card's own entity) highlighted, on top unless they
// rank among the shown rows, `hl` entities highlighted among the rows, `cols` metric calls added
// via `/metrics`. Every column is keyed the way the backend spells its call.
export const table: CardKind = {
	component: TableCard,
	async load({ rootType, semanticId, params, fetch }) {
		const registry = await fetchRegistry(BE_URL, rootType, fetch);
		if (!registry) error(404, 'card unavailable');
		const { metrics } = registry;
		const query = tableQuery(params, registry.defaultSort);
		const n = intParam(params, 'n', P.n.default, 1, P.n.max);
		const from = intParam(params, 'from', P.from.default, 0, Number.MAX_SAFE_INTEGER);
		const pin = [
			...new Set([semanticId, ...idsParam(params, 'pin', P.pin.max - (semanticId ? 1 : 0))])
		].filter(Boolean);
		const highlighted = new Set([...pin, ...idsParam(params, 'hl', P.hl.max)]);
		const typed = colsParam(params, metrics);

		const { page, pinned } = await fetchCohort(BE_URL, rootType, { ...query, pin, from }, fetch);
		const objection = page.error ?? pinned.error;
		if (objection) error(404, objection);
		if (pinned.rows.length < pin.length) error(404, 'unknown pin');
		const sort = sortColumn(page.meta.columns, query.sort ?? '', metrics);
		if (!sort) error(404, 'card unavailable');
		if (from > 0 && from >= (screenedTop(page.meta) ?? page.meta.total))
			error(404, 'from out of range');

		const ranked = page.rows.slice(0, n);
		const onTop = pinned.rows.filter((p) => !ranked.some((r) => r.dmId === p.dmId));
		const rows = [...onTop, ...ranked];
		if (rows.length === 0) error(404, `no ${prettifyRoot(rootType)} in this cohort`);
		if ([...highlighted].some((id) => !rows.some((r) => r.semanticId === id)))
			error(404, 'hl not among the rows');

		const fetched = await extraValues(rootType, rows, typed, fetch);
		const extra = Object.keys(fetched)
			.filter((key) => key !== sort.key)
			.flatMap((key) => columnOf(key, metrics) ?? []);
		const cohort = [sort.key, ...page.meta.columns.filter((k) => k !== sort.key && !fetched[k])]
			.slice(0, MAX_COLUMNS - extra.length)
			.flatMap((key) => columnOf(key, metrics) ?? []);
		const cols = [...cohort, ...extra];
		const names = await loadNames(cols, fetch);
		const value = (row: tt.TableRow, key: string) =>
			fetched[key] ? fetched[key][row.dmId] : rowValue(row, key);

		const noun = prettifyRoot(rootType);
		const where = query.where ? ` where ${query.where}` : '';
		return {
			props: {
				columns: cols.map(
					(c): TableCardColumn => ({
						label: columnLabel(c.decl, c.args, names),
						sorted: c.key === sort.key
					})
				),
				rows: rows.map(
					(r): TableCardRow => ({
						rank: rankText(r),
						name: htmlToText(r.name),
						values: cols.map((c) => formatMetric(c.decl, value(r, c.key))),
						highlight: highlighted.has(r.semanticId),
						pinned: onTop.includes(r)
					})
				),
				note: cohortNote(noun, from, ranked, page.meta, where)
			},
			caption: `Top ${noun} by ${inSentence(sort, names)}${where}`,
			name: semanticId ? undefined : noun[0].toUpperCase() + noun.slice(1)
		};
	}
};

// `cols` is a comma list of metric calls whose own arguments may be comma-separated
// (`window_papers(2020, 2024)`); each must be a numeric metric of the root with its arguments.
function colsParam(params: URLSearchParams, metrics: tt.MetricDecl[]): Column[] {
	const calls = splitCalls(params.get('cols') ?? '');
	if (calls.length > P.cols.max) error(404, 'too many cols');
	return calls.map((call) => {
		const col = columnOf(call, metrics);
		const valid =
			col &&
			isNumeric(col.decl) &&
			col.args.length === arity(col.decl) &&
			col.args.every((a) => ID_CHARS.test(String(a)));
		if (!valid) error(404, `bad cols: ${call}`);
		return col;
	});
}

function splitCalls(raw: string): string[] {
	const calls: string[] = [];
	let depth = 0;
	let start = 0;
	[...raw].forEach((ch, i) => {
		if (ch === '(') depth++;
		else if (ch === ')') depth--;
		else if (ch === ',' && depth === 0) {
			calls.push(raw.slice(start, i));
			start = i + 1;
		}
	});
	calls.push(raw.slice(start));
	return calls.map((c) => c.trim()).filter(Boolean);
}

// Names of the fields and countries the parameterized columns point at, fetched only when one is
// present.
async function loadNames(cols: Column[], fetchFn: typeof fetch): Promise<Names> {
	const lists = await Promise.all(
		(['subfield', 'country'] as const)
			.filter((p) => cols.some((c) => c.decl.param === p))
			.map((p) => fetchParamEntities(BE_URL, p, fetchFn))
	);
	return Object.assign({}, ...lists.map(namesOf));
}

// The added columns' values for the shown rows, by the key the backend answers each call under.
async function extraValues(
	rootType: tt.RootType,
	rows: tt.TableRow[],
	typed: Column[],
	fetchFn: typeof fetch
): Promise<Record<string, MetricValues>> {
	const got = await Promise.all(
		typed.map((c) => fetchColumnValues(BE_URL, rootType, rows, c, fetchFn))
	);
	const objection = got.find((g) => g.error)?.error;
	if (objection) error(404, objection);
	return Object.fromEntries(got.map((g) => [g.key, g.values]));
}

// A column's name inside a sentence: a plain metric label loses its capital, a field or country
// in a header keeps it.
function inSentence(col: Column, names: Names): string {
	const label = columnLabel(col.decl, col.args, names);
	return col.decl.header ? label : label[0].toLowerCase() + label.slice(1);
}

function cohortNote(
	noun: string,
	from: number,
	ranked: tt.TableRow[],
	meta: tt.SliceMeta,
	where: string
): string {
	const top = screenedTop(meta);
	const screened = top === null ? '' : ` · ranked ${screenedPhrase(top)}`;
	const ranks =
		from === 0
			? `Top ${ranked.length}`
			: `Ranks ${rankText(ranked[0])}–${rankText(ranked[ranked.length - 1])}`;
	return `${ranks} of ${meta.total.toLocaleString()} ${noun}${screened}${where ? ` ·${where}` : ''}`;
}
