import { describe, expect, it } from 'vitest';
import type { MetricDecl, TableRow } from '$lib/tree-types';
import type { TableCardColumn, TableCardRow } from '$lib/components/cards/TableCard.svelte';
import type { CardContext } from './kind';
import { table } from './table';

type Props = { columns: TableCardColumn[]; rows: TableCardRow[]; note: string };

const field = (id: string, type: 'count' | 'score', header: string): MetricDecl => ({
	id,
	label: id,
	header,
	meaning: '',
	value: { type },
	param: 'subfield',
	cost: 'read',
	kind: 'global'
});
const metrics: MetricDecl[] = [
	{
		id: 'citations',
		label: 'Citations',
		meaning: '',
		value: { type: 'count' },
		cost: 'read',
		kind: 'global'
	},
	field('field_score', 'score', '{subfield} score'),
	field('field_citations', 'count', '{subfield} citations')
];
const TOTAL = 500;

// The backend keys a call by the semantic id of the entity its argument names.
const canonical = (call: string) =>
	call.replace(/\((.*)\)/, (_, arg: string) => `(${arg.toLowerCase()})`);

function row(i: number, columns: string[]): TableRow {
	return {
		name: `Institution ${i}`,
		semanticId: `inst-${i}`,
		papers: 10,
		citations: 1000 - i,
		oaId: i,
		dmId: i,
		rank: i + 1,
		values: Object.fromEntries(columns.map((c, k) => [c, 1000 - i + k]))
	};
}

// A backend of 500 institutions ranked in id order, and the urls it was asked for.
function backend() {
	const asked: string[] = [];
	const fetchFn = (async (input: string) => {
		const url = new URL(input);
		asked.push(url.pathname + url.search);
		const path = url.pathname.replace('/v1', '');
		const answer = (body: unknown) => new Response(JSON.stringify(body));
		if (path === '/columns')
			return answer({ roots: { institutions: { defaultSort: 'citations', metrics } } });
		if (path === '/slice/subfields/0/400')
			return answer({ rows: [{ name: 'Oncology', semanticId: 'oncology', dmId: 1 }] });
		if (path.startsWith('/metrics/')) {
			const ids = url.searchParams.get('ids')!.split(',').map(Number);
			const key = canonical(url.searchParams.get('metrics')!);
			return answer({ ids, values: { [key]: ids.map((id) => id + 0.5) } });
		}
		const [from, to] = path.split('/').slice(3).map(Number);
		const sort = canonical(url.searchParams.get('sort')!);
		const columns =
			sort === 'citations'
				? ['citations']
				: ['citations', 'field_score(oncology)', 'field_citations(oncology)'];
		const pins = url.searchParams.get('pin')?.split(',') ?? [];
		const ids = pins.length
			? pins.filter((p) => /^inst-\d+$/.test(p)).map((p) => Number(p.split('-')[1]))
			: Array.from({ length: Math.min(to, TOTAL) - from }, (_, k) => from + k);
		return answer({
			rows: ids.map((i) => row(i, columns)),
			meta: { total: TOTAL, screened: null, columns }
		});
	}) as typeof fetch;
	return { asked, fetchFn };
}

async function load(query: string, be = backend()): Promise<Props> {
	const ctx = {
		rootType: 'institutions',
		semanticId: '',
		params: new URLSearchParams(query),
		fetch: be.fetchFn
	} as CardContext;
	return (await table.load(ctx)).props as Props;
}

describe('table card', () => {
	it('reads the sorted column under the backend spelling of the ranking call', async () => {
		const { columns, rows } = await load('sort=field_score(Oncology)');
		expect(columns.map((c) => [c.label, c.sorted])).toEqual([
			['Oncology score', true],
			['Citations', false],
			['Oncology citations', false]
		]);
		expect(rows[0].values).toEqual(['1,001', '1,000', '1,002']);
	});

	it('shows an added column once, under the backend spelling, with its own values', async () => {
		const { columns, rows } = await load(
			'sort=field_score(oncology)&cols=field_citations(Oncology)'
		);
		expect(columns.map((c) => c.label)).toEqual([
			'Oncology score',
			'Citations',
			'Oncology citations'
		]);
		expect(rows[0].values).toEqual(['1,001', '1,000', '1']);
	});

	it('shows the ranks from `from` on and says which they are', async () => {
		const be = backend();
		const { rows, note } = await load('from=50&n=3', be);
		expect(be.asked).toContain('/v1/slice/institutions/50/150?sort=citations');
		expect(rows.map((r) => r.rank)).toEqual(['51', '52', '53']);
		expect(note).toBe('Ranks 51–53 of 500 institutions');
		await expect(load('from=500')).rejects.toMatchObject({ status: 404 });
	});

	it('keeps the pinned entities on top of the ranked rows they are not among', async () => {
		const { rows } = await load('pin=inst-2,inst-40&n=3');
		expect(rows.map((r) => [r.rank, r.pinned])).toEqual([
			['41', true],
			['1', false],
			['2', false],
			['3', false]
		]);
		expect(rows.filter((r) => r.highlight).map((r) => r.rank)).toEqual(['41', '3']);
	});

	it('refuses a pin the type lacks and a highlight that is not on the card', async () => {
		await expect(load('pin=inst-2,nope')).rejects.toMatchObject({ status: 404 });
		await expect(load('hl=inst-400&n=3')).rejects.toMatchObject({ status: 404 });
		expect((await load('hl=inst-1&n=3')).rows.map((r) => r.highlight)).toEqual([
			false,
			true,
			false
		]);
	});
});
