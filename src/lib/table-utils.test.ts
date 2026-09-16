import { describe, it, expect } from 'vitest';
import {
	columnKey,
	formatMetric,
	globalColumns,
	metricValuesUrl,
	metricsFor,
	rowValue,
	sortRows,
	tableHref,
	validSort
} from './table-utils';
import type { MetricDecl, TableRow } from './tree-types';

const registry: MetricDecl[] = [
	{ id: 'citations', label: 'Citations', meaning: 'c', kinds: { authors: 'global' }, params: [] },
	{
		id: 'field_score',
		label: 'Field score',
		meaning: 'f',
		kinds: { authors: 'intricate', institutions: 'global' },
		params: ['subfield']
	},
	{
		id: 'window_papers',
		label: 'Papers in window',
		meaning: 'w',
		kinds: { authors: 'intricate', institutions: 'intricate' },
		params: ['year_from', 'year_to']
	}
];

describe('table column model', () => {
	it('splits the registry by kind per root type', () => {
		expect(metricsFor(registry, 'authors', 'global').map((m) => m.id)).toEqual(['citations']);
		expect(metricsFor(registry, 'authors', 'intricate').map((m) => m.id)).toEqual([
			'field_score',
			'window_papers'
		]);
		expect(metricsFor(registry, 'institutions', 'global').map((m) => m.id)).toEqual([
			'field_score'
		]);
	});

	it('shows field columns only once a subfield narrows the cohort', () => {
		expect(globalColumns(registry, 'institutions', false)).toEqual([]);
		expect(globalColumns(registry, 'institutions', true).map((m) => m.id)).toEqual(['field_score']);
	});

	it('falls back to citations for a sort the server cannot serve', () => {
		expect(validSort(registry, 'institutions', 'field_score', 'oncology')).toBe('field_score');
		expect(validSort(registry, 'institutions', 'field_score', '')).toBe('citations');
		expect(validSort(registry, 'authors', 'field_score', 'oncology')).toBe('citations');
		expect(validSort(registry, 'authors', 'nonsense', '')).toBe('citations');
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
		impactScore: 12.345,
		fieldScore: 0.5
	};

	it('maps metric ids onto row fields', () => {
		expect(rowValue(row, 'impact_score')).toBe(12.345);
		expect(rowValue(row, 'field_score')).toBe(0.5);
		expect(rowValue(row, 'h_index')).toBeUndefined();
		expect(rowValue(row, 'window_papers')).toBeUndefined();
	});

	it('formats by metric', () => {
		expect(formatMetric('impact_score', 12.345)).toBe('12.3');
		expect(formatMetric('impact_score', 0.456)).toBe('0.46');
		expect(formatMetric('impact_score', 1234.5)).toBe('1,235');
		expect(formatMetric('citing_country_share', 0.1234)).toBe('12.3%');
		expect(formatMetric('year_centroid', 2011.26)).toBe('2011.3');
		expect(formatMetric('window_papers', 1500)).toBe('1,500');
		expect(formatMetric('window_papers', null)).toBe('–');
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
	it('keys a column by metric and parameters', () => {
		expect(columnKey('window_papers', { year_to: 2024, year_from: 2020 })).toBe(
			'window_papers|year_from=2020|year_to=2024'
		);
		expect(columnKey('field_score', { subfield: '' })).toBe('field_score');
	});

	it('builds the table href without defaults', () => {
		expect(tableHref('authors', { sort: 'citations' })).toBe('/authors/table');
		expect(tableHref('authors', { sort: 'impact_score', subfield: 'oncology', from: 100 })).toBe(
			'/authors/table?sort=impact_score&subfield=oncology&from=100'
		);
	});

	it('carries every id of the page in one metric-values call', () => {
		expect(
			metricValuesUrl('http://be/v1', 'authors', [1, 2, 3], 'window_papers', {
				year_from: 2020,
				year_to: 2024
			})
		).toBe(
			'http://be/v1/metrics/authors?ids=1%2C2%2C3&metrics=window_papers&year_from=2020&year_to=2024'
		);
	});
});
