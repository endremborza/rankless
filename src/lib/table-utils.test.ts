import type { Expr } from './wire/rankless_expr';
import type { ColumnDecl, TableRow } from './wire/rankless_server/responses';
import type { Kind } from './wire/rankless_trees/metrics';
import { describe, it, expect } from 'vitest';
import {
	annotatable,
	argsReady,
	callText,
	chipLabel,
	chipsFrom,
	DEFAULT_WINDOW_YEARS,
	defaultArgs,
	clauseable,
	clauseText,
	columnLabel,
	columnOf,
	fetchCohort,
	fetchColumnValues,
	formatMetric,
	metricValuesUrl,
	operatorsFor,
	parseCall,
	rankable,
	rankText,
	rowValue,
	screenedPhrase,
	screenedTop,
	sortColumn,
	sortRows,
	tableHref,
	tableQuery,
	whereText
} from './table-utils';

type Root = 'authors' | 'institutions';
type Decl = Omit<ColumnDecl, 'kind'> & { kinds: Partial<Record<Root, Kind>> };

// One declaration per metric with its kind per root, served as each root's registry.
const decls: Decl[] = [
	{
		id: 'citations',
		label: 'Citations',
		meaning: 'c',
		value: { type: 'count' },
		cost: 'read',
		kinds: { authors: 'global', institutions: 'global' }
	},
	{
		id: 'top_mean',
		label: 'Top-20 mean',
		meaning: 't',
		value: { type: 'score' },
		cost: 'read',
		kinds: { authors: 'global', institutions: 'global' }
	},
	{
		id: 'field_score',
		label: 'Field score',
		header: '{subfield} score',
		meaning: 'f',
		value: { type: 'score' },
		param: 'subfield',
		cost: 'read',
		kinds: { authors: 'intricate', institutions: 'global' }
	},
	{
		id: 'window_papers',
		label: 'Papers in a year window',
		header: 'Papers {window}',
		meaning: 'w',
		value: { type: 'count' },
		param: 'window',
		cost: 'read',
		kinds: { authors: 'global', institutions: 'global' }
	},
	{
		id: 'cited_from',
		label: 'Share cited from a country',
		header: 'Cited from {country}',
		meaning: 's',
		value: { type: 'share' },
		param: 'country',
		cost: 'walk',
		kinds: { authors: 'intricate' }
	},
	{
		id: 'country',
		label: 'Country',
		meaning: 'k',
		value: { type: 'entities', entity: 'countries' },
		cost: 'read',
		kinds: { authors: 'global', institutions: 'global' }
	}
];
const registryOf = (root: Root): ColumnDecl[] =>
	decls.flatMap(({ kinds, ...d }) => (kinds[root] ? [{ ...d, kind: kinds[root] }] : []));
const registry = registryOf('authors');
const institutions = registryOf('institutions');

const ids = (ms: ColumnDecl[]) => ms.map((m) => m.id);
const names = { oncology: 'Oncology', hun: 'Hungary', can: 'Canada' };

describe('table column model', () => {
	it('ranks by every numeric column read, never by a walk or an entity', () => {
		expect(ids(rankable(institutions))).toEqual([
			'citations',
			'top_mean',
			'field_score',
			'window_papers'
		]);
		expect(ids(rankable(registry))).toEqual([
			'citations',
			'top_mean',
			'field_score',
			'window_papers'
		]);
	});

	it('offers as page-local columns what the rows do not carry by themselves', () => {
		expect(ids(annotatable(institutions))).toEqual(['field_score', 'window_papers']);
		expect(ids(annotatable(registry))).toEqual(['field_score', 'window_papers', 'cited_from']);
	});

	it('narrows by every column read, entities included, never by a walk', () => {
		expect(ids(clauseable(registry))).toEqual([
			'citations',
			'top_mean',
			'field_score',
			'window_papers',
			'country'
		]);
		expect(operatorsFor(registry[0])).toEqual(['ge', 'le', 'gt', 'lt', 'eq', 'ne']);
		expect(operatorsFor(registry[5])).toEqual(['eq', 'ne']);
	});

	it('names a column by its argument, the chosen entity by name where known', () => {
		expect(columnLabel(registry[0])).toBe('Citations');
		expect(columnLabel(registry[3], [2020, 2024])).toBe('Papers 2020–2024');
		expect(columnLabel(registry[4], ['can'], names)).toBe('Cited from Canada');
		expect(columnLabel(registry[4], ['can'])).toBe('Cited from can');
	});

	it('reads a call as a column of the root, none for a metric the root lacks', () => {
		expect(columnOf('field_score(oncology)', registry)).toEqual({
			key: 'field_score(oncology)',
			decl: registry[2],
			args: ['oncology']
		});
		expect(columnOf('cited_from(can)', institutions)).toBeNull();
	});

	it('finds the ranked column under the backend spelling, ahead of any the filter adds', () => {
		const columns = ['citations', 'field_score(oncology)', 'field_score(biology)'];
		expect(sortColumn(columns, 'field_score(Oncology)', registry)?.key).toBe(
			'field_score(oncology)'
		);
		expect(sortColumn(['citations'], 'top_mean', registry)?.key).toBe('top_mean');
		expect(sortColumn(columns, 'nope', registry)).toBeNull();
	});
});

describe('calls and clauses', () => {
	it('spells a call the way the backend does and reads it back', () => {
		expect(callText('papers', [])).toBe('papers');
		expect(callText('field_score', ['oncology'])).toBe('field_score(oncology)');
		expect(callText('window_papers', [2020, 2024])).toBe('window_papers(2020, 2024)');
		expect(callText('city', ['new york'])).toBe('city("new york")');
		expect(parseCall('window_papers(2020, 2024)')).toEqual({
			metric: 'window_papers',
			args: [2020, 2024]
		});
		expect(parseCall('field_score(oncology)')).toEqual({
			metric: 'field_score',
			args: ['oncology']
		});
		expect(parseCall('city("new york")')).toEqual({ metric: 'city', args: ['new york'] });
		expect(parseCall('papers')).toEqual({ metric: 'papers', args: [] });
	});

	it('a call is ready when every argument its parameter takes is given', () => {
		const window = registry.find((d) => d.id === 'window_papers')!;
		const field = registry.find((d) => d.id === 'field_score')!;
		const papers = registry.find((d) => d.id === 'citations')!;
		expect(argsReady(window, [2016, 2026])).toBe(true);
		expect(argsReady(window, [2020, ''])).toBe(false);
		expect(argsReady(window, [2020])).toBe(false);
		expect(argsReady(window, [])).toBe(false);
		expect(argsReady(field, ['oncology'])).toBe(true);
		expect(argsReady(field, [])).toBe(false);
		expect(argsReady(papers, [])).toBe(true);
	});

	it('a window starts on the default span of counted years unless one is given', () => {
		const window = registry.find((d) => d.id === 'window_papers')!;
		const field = registry.find((d) => d.id === 'field_score')!;
		const last = 2026;
		const start = last - DEFAULT_WINDOW_YEARS;
		expect(defaultArgs(window, [], [2016, last])).toEqual([start, last]);
		const shortHistory: [number, number] = [last - DEFAULT_WINDOW_YEARS + 1, last];
		expect(defaultArgs(window, [], shortHistory)).toEqual(shortHistory);
		expect(defaultArgs(window, [2018, 2020], [2016, last])).toEqual([2018, 2020]);
		expect(defaultArgs(window, ['oncology'], [2016, last])).toEqual([start, last]);
		expect(defaultArgs(window, [])).toEqual([]);
		expect(defaultArgs(field, [2018, 2020])).toEqual([]);
		expect(defaultArgs(field, ['oncology'])).toEqual(['oncology']);
	});

	it('serializes chips into one conjunction and labels them by name', () => {
		const chips = [
			{ call: 'country', op: 'eq' as const, operand: 'hun' },
			{ call: 'papers', op: 'ge' as const, operand: 500 },
			{ call: 'city', op: 'ne' as const, operand: 'new york' },
			{ call: 'country', op: 'in' as const, operand: ['hun', 'can'] }
		];
		expect(clauseText(chips[2])).toBe('city != "new york"');
		expect(whereText(chips)).toBe(
			'country = hun and papers >= 500 and city != "new york" and country in (hun, can)'
		);
		expect(chipLabel(chips[0], registry, names)).toBe('Country = Hungary');
		expect(chipLabel(chips[1], registry, names)).toBe('papers ≥ 500');
		expect(
			chipLabel({ call: 'field_score(oncology)', op: 'gt', operand: 0 }, registry, names)
		).toBe('Oncology score > 0');
		expect(chipLabel(chips[3], registry, names)).toBe('Country in (Hungary, Canada)');
	});

	it('shows a flat conjunction as chips and anything else as text', () => {
		const flat: Expr = {
			and: [
				{ clause: { call: { metric: 'country', args: [] }, op: 'eq', operand: 'hun' } },
				{ clause: { call: { metric: 'field_score', args: ['oncology'] }, op: 'gt', operand: 1 } }
			]
		};
		expect(chipsFrom(flat)).toEqual([
			{ call: 'country', op: 'eq', operand: 'hun' },
			{ call: 'field_score(oncology)', op: 'gt', operand: 1 }
		]);
		const single: Expr = {
			clause: { call: { metric: 'papers', args: [] }, op: 'ge', operand: 5 }
		};
		expect(chipsFrom(single)).toEqual([{ call: 'papers', op: 'ge', operand: 5 }]);
		expect(chipsFrom({ or: [single, single] })).toBeNull();
		expect(chipsFrom({ and: [single, { not: single }] })).toBeNull();
		expect(chipsFrom(null)).toEqual([]);
	});
});

describe('row values and formatting', () => {
	const row: TableRow = {
		name: 'x',
		semanticId: 'x',
		papers: 3,
		citations: 30,
		oaId: 1,
		dmId: 7,
		rank: 2,
		values: { top_mean: 12.345, 'field_score(oncology)': 0.5 }
	};

	it('reads a column by its call', () => {
		expect(rowValue(row, 'top_mean')).toBe(12.345);
		expect(rowValue(row, 'field_score(oncology)')).toBe(0.5);
		expect(rowValue(row, 'h_index')).toBeUndefined();
	});

	it('reads a page-local column under the spelling the backend answers with', async () => {
		const answer = { ids: [7, 9], values: { 'field_score(oncology)': [0.5, null] } };
		const fetchFn = (async () => new Response(JSON.stringify(answer))) as typeof fetch;
		const col = columnOf('field_score(Oncology)', registry)!;
		const rows = [row, { ...row, dmId: 9 }];
		expect(await fetchColumnValues('http://be/v1', 'authors', rows, col, fetchFn)).toEqual({
			key: 'field_score(oncology)',
			values: { 7: 0.5, 9: null },
			error: null
		});
	});

	it('shows a rank, a dash for a pinned entity outside the ranking', () => {
		expect(rankText({ ...row, rank: 1234 })).toBe('1,234');
		expect(rankText({ ...row, rank: null })).toBe('–');
	});

	it('names the top a screened ordering ranked', () => {
		expect(screenedTop({ total: 5000, screened: 1000 })).toBe(1000);
		expect(screenedTop({ total: 800, screened: 800 })).toBeNull();
		expect(screenedTop({ total: 5000, screened: null })).toBeNull();
		expect(screenedPhrase(1000)).toBe('among the top 1,000 by citations');
	});

	it('formats by value type', () => {
		expect(formatMetric(registry[1], 12.345)).toBe('12.3');
		expect(formatMetric(registry[1], 0.456)).toBe('0.46');
		expect(formatMetric(registry[1], 1234.5)).toBe('1,235');
		expect(formatMetric(registry[4], 0.1234)).toBe('12.3%');
		expect(formatMetric(registry[4], 0.0003)).toBe('0.03%');
		expect(formatMetric(registry[0], 1500)).toBe('1,500');
		expect(formatMetric(undefined, 1500.4)).toBe('1,500');
		expect(formatMetric(registry[0], null)).toBe('–');
	});
});

describe('page-local sort', () => {
	it('is stable and keeps missing values last in both directions', () => {
		const rows = [
			{ id: 'a', v: 1 },
			{ id: 'b', v: null },
			{ id: 'c', v: 3 },
			{ id: 'd', v: 3 }
		];
		expect(sortRows(rows, (r) => r.v, false).map((r) => r.id)).toEqual(['c', 'd', 'a', 'b']);
		expect(sortRows(rows, (r) => r.v, true).map((r) => r.id)).toEqual(['a', 'c', 'd', 'b']);
	});
});

describe('urls', () => {
	it('builds the table href without defaults, the query as the backend takes it', () => {
		const byDefault = 'weighted_paper_score';
		expect(tableHref('authors', { sort: byDefault, pin: [] }, byDefault)).toBe('/authors/table');
		expect(tableHref('authors', { sort: 'citations' }, byDefault)).toBe(
			'/authors/table?sort=citations'
		);
		expect(
			tableHref('authors', { sort: 'field_score(oncology)', where: 'country = hun', from: 100 })
		).toBe('/authors/table?sort=field_score%28oncology%29&where=country+%3D+hun&from=100');
		expect(tableHref('authors', { pin: ['a-1', 'b-2'] })).toBe('/authors/table?pin=a-1%2Cb-2');
	});

	it('reads a table URL as typed, the root default when it names no ordering', () => {
		expect(tableQuery(new URLSearchParams('where=papers > 3'), 'top_mean')).toEqual({
			sort: 'top_mean',
			where: 'papers > 3'
		});
		expect(tableQuery(new URLSearchParams('sort=field_score(Oncology)'), 'top_mean')).toEqual({
			sort: 'field_score(Oncology)',
			where: ''
		});
	});

	it('fetches the page without the pins and the pinned rows in the same ordering', async () => {
		const urls: string[] = [];
		const empty = { rows: [], meta: { total: 0, screened: null, columns: [] } };
		const fetchFn = (async (url: string) => {
			urls.push(url);
			return new Response(JSON.stringify(empty));
		}) as typeof fetch;
		await fetchCohort('http://be/v1', 'authors', { sort: 'citations' }, fetchFn);
		expect(urls).toEqual(['http://be/v1/slice/authors/0/100?sort=citations']);
		urls.length = 0;
		const q = { sort: 'citations', pin: ['a-1'], from: 200 };
		await fetchCohort('http://be/v1', 'authors', q, fetchFn);
		expect(urls).toEqual([
			'http://be/v1/slice/authors/200/300?sort=citations',
			'http://be/v1/slice/authors/0/100?sort=citations&pin=a-1'
		]);
	});

	it('carries every id of the page and the call in one metric-values call', () => {
		expect(metricValuesUrl('http://be/v1', 'authors', [1, 2, 3], 'window_papers(2020, 2024)')).toBe(
			'http://be/v1/metrics/authors?ids=1%2C2%2C3&metrics=window_papers%282020%2C+2024%29'
		);
	});
});
