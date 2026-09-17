<script lang="ts">
	import { untrack } from 'svelte';
	import { goto } from '$app/navigation';
	import type { PageData } from './$types';
	import { APP_NAME, BE_REMOTE_URL, COHORT_ROOT_TYPES } from '$lib/constants';
	import { prettifyRoot } from '$lib/text-format-util';
	import { entToLink } from '$lib/tree-functions';
	import { citStandingTier, standingLabel, tierLabels } from '$lib/peers-utils';
	import {
		columnLabel,
		fetchColumnValues,
		fetchSlice,
		fieldFilterable,
		formatMetric,
		globalColumns,
		metricsFor,
		rowValue,
		sortRows,
		tableHref,
		type IntricateColumn,
		type MetricValues,
		type TableQuery
	} from '$lib/table-utils';
	import ColumnAdder from '$lib/components/ColumnAdder.svelte';
	import EntityPins from '$lib/components/EntityPins.svelte';
	import InfoTip from '$lib/components/InfoTip.svelte';
	import type { TableRow } from '$lib/tree-types';

	let { data }: { data: PageData } = $props();

	type PageExtension = { of: TableRow[]; rows: TableRow[]; done: boolean };

	// Rows loaded past the server-rendered page, tied to the page they extend: a navigation loads new
	// data into this same component instance, and a render with the new rows drops the old extension
	// before it can collide with them. untrack marks the seed read.
	let extra = $state.raw<PageExtension>({ of: untrack(() => data.rows), rows: [], done: false });
	let loadingMore = $state(false);

	// Page-local columns: intricate metrics evaluated for the rows on screen, one call per column
	// per loaded page, never one per row. Values are keyed by column then by dm id.
	let columns = $state<IntricateColumn[]>([]);
	let values = $state<Record<string, MetricValues>>({});
	let loadingColumns = $state(0);
	let localSort = $state<{ key: string; asc: boolean } | null>(null);

	$effect(() => {
		const rows = [...data.pinned, ...data.rows];
		untrack(() => {
			localSort = null;
			columns.forEach((c) => fillColumn(c, rows));
		});
	});

	const extension = $derived(
		extra.of === data.rows ? extra : { of: data.rows, rows: [], done: false }
	);
	const pinnedIds = $derived(new Set(data.pinned.map((r) => r.dmId)));
	const pageRows = $derived(
		[...data.rows, ...extension.rows].filter((r) => !pinnedIds.has(r.dmId))
	);
	const loaded = $derived(data.rows.length + extension.rows.length);
	const noMore = $derived(extension.done || data.rows.length < data.pageSize);
	const field = $derived(data.subfields.find((s) => s.semanticId === data.subfield));
	const names = $derived({ subfield: field?.name });
	const globals = $derived(globalColumns(data.registry, data.rootType, field !== undefined));
	const intricates = $derived(metricsFor(data.registry, data.rootType, 'intricate'));
	const narrowable = $derived(fieldFilterable(data.registry, data.rootType));
	const hasStanding = $derived(field !== undefined && data.ladder !== null);
	const tierNames = $derived(data.ladder ? tierLabels(data.ladder.pctBands) : []);
	const sortDecl = $derived(data.registry.find((m) => m.id === data.sort));
	const sortLabel = $derived(sortDecl ? columnLabel(sortDecl, {}, names) : data.sort);
	const noun = $derived(prettifyRoot(data.rootType));
	const span = $derived(2 + globals.length + (hasStanding ? 1 : 0) + columns.length);
	const displayed = $derived.by(() => {
		const ls = localSort;
		return ls ? sortRows(pageRows, (r) => values[ls.key]?.[r.dmId], ls.asc) : pageRows;
	});
	const title = $derived(`${APP_NAME} | ${noun} table`);

	function standing(row: TableRow): string {
		if (!data.ladder || field?.dmId === undefined) return '';
		const tier = citStandingTier(data.ladder.ladder[field.dmId] ?? [], row.fieldCitations ?? 0);
		return standingLabel(tier, tierNames) ?? '';
	}

	function go(patch: TableQuery) {
		const q = { sort: data.sort, subfield: data.subfield, pin: data.pin, ...patch };
		goto(tableHref(data.rootType, q));
	}

	function toggleLocalSort(key: string) {
		localSort = localSort?.key === key ? { key, asc: !localSort.asc } : { key, asc: false };
	}

	async function fillColumn(col: IntricateColumn, rows: TableRow[]) {
		if (rows.length === 0) return;
		loadingColumns += 1;
		const got = await fetchColumnValues(BE_REMOTE_URL, data.rootType, rows, col);
		values = { ...values, [col.key]: { ...values[col.key], ...got } };
		loadingColumns -= 1;
	}

	function addColumn(col: IntricateColumn) {
		if (columns.some((c) => c.key === col.key)) return;
		columns = [...columns, col];
		fillColumn(col, [...data.pinned, ...pageRows]);
	}

	function removeColumn(key: string) {
		columns = columns.filter((c) => c.key !== key);
		if (localSort?.key === key) localSort = null;
	}

	async function loadMore() {
		if (loadingMore || noMore) return;
		loadingMore = true;
		const of = data.rows;
		const q = { sort: data.sort, subfield: data.subfield };
		const { rows } = await fetchSlice(BE_REMOTE_URL, data.rootType, data.from + loaded, q);
		loadingMore = false;
		if (of !== data.rows) return;
		extra = { of, rows: [...extension.rows, ...rows], done: rows.length < data.pageSize };
		columns.forEach((c) => fillColumn(c, rows));
	}
</script>

<svelte:head>
	<title>{title}</title>
</svelte:head>

{#snippet tr(row: TableRow, pinned: boolean)}
	<tr class:pinned>
		<td class="col-rank">{row.rank?.toLocaleString() ?? '–'}</td>
		<td class="col-name">
			<a href={entToLink({ rootType: data.rootType, semanticId: row.semanticId })}
				>{@html row.name}</a
			>
			{#if row.distinctText}
				<span class="distinct">{row.distinctText}</span>
			{/if}
			{#if pinned && row.rank === null}
				<span class="distinct">not active in {field?.name}</span>
			{/if}
		</td>
		{#each globals as m (m.id)}
			<td class="num">{formatMetric(m.id, rowValue(row, m.id))}</td>
		{/each}
		{#if hasStanding}
			<td class="num standing">{standing(row)}</td>
		{/if}
		{#each columns as col (col.key)}
			<td class="num local">{formatMetric(col.metric.id, values[col.key]?.[row.dmId])}</td>
		{/each}
	</tr>
{/snippet}

<div class="table-page shadowy padded marged">
	<nav class="root-switch" aria-label="Table of">
		{#each COHORT_ROOT_TYPES as rt, i (i)}
			<a href={tableHref(rt, {})} class:active={rt === data.rootType}>{prettifyRoot(rt)}</a>
		{/each}
	</nav>
	<h1>{noun}</h1>
	<p class="cohort-note">
		{loaded.toLocaleString()} of {data.total.toLocaleString()}
		{noun}{#if field}
			active in {field.name}{/if}, ranked by {sortLabel}. Click a column to re-rank all of them.
	</p>

	<div class="filters">
		{#if narrowable}
			<select
				class="control"
				aria-label="Narrow to a field"
				value={data.subfield}
				onchange={(e) => go({ subfield: e.currentTarget.value })}
			>
				<option value="">All fields</option>
				{#each data.subfields as sf, i (i)}
					<option value={sf.semanticId}>{sf.name}</option>
				{/each}
			</select>
		{/if}
		<EntityPins
			rootType={data.rootType}
			pins={data.pin}
			rows={data.pinned}
			onchange={(pin) => go({ pin })}
		/>
	</div>
	<ColumnAdder metrics={intricates} subfields={data.subfields} onadd={addColumn} />

	<div class="table-wrap">
		<table>
			<thead>
				<tr>
					<th colspan="2"></th>
					<th colspan={globals.length + (hasStanding ? 1 : 0)} class="group">
						All {data.total.toLocaleString()}
						{noun}
					</th>
					{#if columns.length > 0}
						<th colspan={columns.length} class="group local">The loaded rows only</th>
					{/if}
				</tr>
				<tr>
					<th class="col-rank">#</th>
					<th class="col-name">Name</th>
					{#each globals as m (m.id)}
						<th
							class="num sortable"
							class:active={data.sort === m.id}
							aria-sort={data.sort === m.id ? 'descending' : undefined}
							onclick={() => go({ sort: m.id })}
						>
							{columnLabel(m, {}, names)}{data.sort === m.id ? ' ↓' : ''}
							<InfoTip text={m.meaning} label={m.label} />
						</th>
					{/each}
					{#if hasStanding}
						<th class="num">
							Standing
							<InfoTip
								text="The most selective percentile band the entity's {field?.name} citations reach among all {noun} active in the field."
								label="Standing"
							/>
						</th>
					{/if}
					{#each columns as col (col.key)}
						<th
							class="num sortable local"
							class:active={localSort?.key === col.key}
							onclick={() => toggleLocalSort(col.key)}
						>
							{col.label}{localSort?.key === col.key ? (localSort.asc ? ' ↑' : ' ↓') : ''}
							<InfoTip
								text="{col.metric
									.meaning} Computed for the loaded rows only; sorting by it reorders this page, not the ranking."
								label={col.label}
							/>
							<button
								class="remove"
								type="button"
								aria-label="Remove column {col.label}"
								onclick={(e) => {
									e.stopPropagation();
									removeColumn(col.key);
								}}>×</button
							>
						</th>
					{/each}
				</tr>
			</thead>
			<tbody>
				{#each data.pinned as row (row.dmId)}
					{@render tr(row, true)}
				{/each}
				{#each displayed as row (row.dmId)}
					{@render tr(row, false)}
				{/each}
				{#if displayed.length === 0}
					<tr><td colspan={span} class="empty">No {noun} in this cohort</td></tr>
				{/if}
			</tbody>
		</table>
	</div>

	{#if loadingColumns > 0}
		<p class="cohort-note">Computing page-local columns…</p>
	{/if}

	{#if !noMore}
		<button class="load-more" onclick={loadMore} disabled={loadingMore}>
			{loadingMore ? 'Loading…' : `Load more (showing ${loaded.toLocaleString()})`}
		</button>
	{/if}
</div>

<style>
	.table-page {
		margin-top: var(--unified-margin);
		margin-bottom: var(--unified-margin);
	}

	.root-switch {
		display: flex;
		gap: 12px;
		flex-wrap: wrap;
		font-size: var(--text-sm);
		text-transform: capitalize;
	}

	.root-switch a {
		color: var(--color-text);
		text-decoration: none;
		opacity: 0.6;
	}

	.root-switch a:hover,
	.root-switch a.active {
		opacity: 1;
		text-decoration: underline;
	}

	h1 {
		margin: 4px 0 0;
		text-transform: capitalize;
	}

	.cohort-note {
		font-size: var(--text-sm);
		opacity: 0.6;
		margin: 4px 0 12px;
	}

	.filters {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
		align-items: center;
		margin-bottom: 8px;
	}

	.table-wrap {
		overflow-x: auto;
		margin-top: 12px;
	}

	table {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--text-base);
	}

	thead th {
		text-align: left;
		padding: 6px 8px;
		border-bottom: 2px solid rgba(var(--color-range-15), 0.15);
		white-space: nowrap;
		font-size: var(--text-sm);
		opacity: 0.6;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	th.group {
		text-align: center;
		font-size: var(--text-xs);
		text-transform: none;
		letter-spacing: 0;
		border-bottom: 1px solid rgba(var(--color-range-15), 0.3);
	}

	th.group.local,
	th.local,
	td.local {
		border-left: 1px solid rgba(var(--color-range-15), 0.2);
	}

	thead th.sortable {
		cursor: pointer;
		user-select: none;
	}

	thead th.sortable:hover,
	thead th.active {
		opacity: 1;
	}

	.remove {
		border: none;
		background: none;
		color: inherit;
		cursor: pointer;
		font-size: var(--text-base);
		margin-left: 2px;
		padding: 0 2px;
	}

	tbody tr {
		border-bottom: 1px solid rgba(var(--color-range-15), 0.06);
	}

	tbody tr:hover {
		background: rgba(var(--color-range-15), 0.04);
	}

	tbody tr.pinned {
		background: rgba(var(--color-range-15), 0.07);
	}

	td {
		padding: 6px 8px;
		vertical-align: middle;
	}

	.col-rank {
		width: 48px;
		text-align: right;
		font-size: var(--text-xs);
		opacity: 0.35;
		font-variant-numeric: tabular-nums;
	}

	.col-name a {
		color: var(--color-text);
		text-decoration: none;
	}

	.col-name a:hover {
		text-decoration: underline;
	}

	.distinct {
		font-size: var(--text-xs);
		opacity: 0.45;
		margin-left: 6px;
		font-style: italic;
	}

	.num {
		text-align: right;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
	}

	td.local {
		opacity: 0.8;
	}

	.standing {
		font-size: var(--text-sm);
	}

	.empty {
		text-align: center;
		padding: 24px;
		opacity: 0.4;
		font-style: italic;
	}

	.load-more {
		display: block;
		margin: 16px auto 0;
		padding: 6px 20px;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		background: none;
		cursor: pointer;
		font-size: var(--text-sm);
		color: var(--color-text);
		font-family: inherit;
	}

	.load-more:hover:not(:disabled) {
		background: rgba(var(--color-range-15), 0.05);
	}

	.load-more:disabled {
		opacity: 0.4;
		cursor: default;
	}
</style>
