<script lang="ts">
	import { untrack } from 'svelte';
	import { goto } from '$app/navigation';
	import type { PageData } from './$types';
	import { APP_NAME, BE_REMOTE_URL, COHORT_ROOT_TYPES } from '$lib/constants';
	import { prettifyRoot, workScreenPhrase } from '$lib/text-format-util';
	import { entToLink } from '$lib/tree-functions';
	import { citStandingTier, standingLabel, tierLabels } from '$lib/peers-utils';
	import {
		annotatable,
		callText,
		clauseable,
		columnLabel,
		fetchColumnValues,
		fetchSlice,
		formatMetric,
		namesOf,
		parseCall,
		rankable,
		rowValue,
		sortRows,
		tableHref,
		type Column,
		type MetricArgs,
		type MetricValues,
		type TableQuery
	} from '$lib/table-utils';
	import ClauseBuilder from '$lib/components/ClauseBuilder.svelte';
	import EntityPins from '$lib/components/EntityPins.svelte';
	import InfoTip from '$lib/components/InfoTip.svelte';
	import MetricPicker from '$lib/components/MetricPicker.svelte';
	import type { MetricDecl, TableRow } from '$lib/tree-types';

	let { data }: { data: PageData } = $props();

	type PageExtension = { of: TableRow[]; rows: TableRow[]; done: boolean };

	// Rows loaded past the server-rendered page, tied to the page they extend: a navigation loads new
	// data into this same component instance, and a render with the new rows drops the old extension
	// before it can collide with them. untrack marks the seed read.
	let extra = $state.raw<PageExtension>({ of: untrack(() => data.rows), rows: [], done: false });
	let loadingMore = $state(false);

	// Page-local columns: metric calls evaluated for the rows on screen, one call per column per
	// loaded page, never one per row. Values are keyed by column then by dm id; a cell without a
	// value is pending while its column has a call in flight, and unknown otherwise.
	let columns = $state<Column[]>([]);
	let values = $state<Record<string, MetricValues>>({});
	let inflight = $state<Record<string, number>>({});
	// The backend's objection to the last page-local column fetched, shown beside the page's own.
	let columnError = $state<string | null>(null);
	// Reorders the loaded rows only, by a cohort column's key or a page-local column's key.
	let localSort = $state<{ key: string; asc: boolean } | null>(null);

	$effect(() => {
		const rows = [...data.pinned, ...data.rows];
		untrack(() => {
			localSort = null;
			columns.forEach((c) => fillColumn(c, rows));
		});
	});

	const q = $derived(data.query);
	const extension = $derived(
		extra.of === data.rows ? extra : { of: data.rows, rows: [], done: false }
	);
	const pinnedIds = $derived(new Set(data.pinned.map((r) => r.dmId)));
	const pageRows = $derived(
		[...data.rows, ...extension.rows].filter((r) => !pinnedIds.has(r.dmId))
	);
	const loaded = $derived(data.rows.length + extension.rows.length);
	const noMore = $derived(extension.done || data.rows.length < data.pageSize);
	const names = $derived({ ...namesOf(data.subfields), ...namesOf(data.countries) });
	const decls = $derived(new Map(data.registry.map((m) => [m.id, m])));
	// The cohort's columns as the backend listed them, each with its metric and arguments.
	const cohortCols = $derived(
		data.columns.flatMap((key) => {
			const { metric, args } = parseCall(key);
			const decl = decls.get(metric);
			return decl ? [{ key, decl, args }] : [];
		})
	);
	const rankings = $derived(rankable(data.registry));
	const addable = $derived(annotatable(data.registry));
	const narrowers = $derived(clauseable(data.registry));
	const fieldName = $derived(names[data.field] ?? data.field);
	const hasStanding = $derived(data.field !== '' && data.ladder !== null);
	const tierNames = $derived(data.ladder ? tierLabels(data.ladder.pctBands) : []);
	const sortCall = $derived(parseCall(q.sort ?? ''));
	const sortDecl = $derived(decls.get(sortCall.metric));
	const sortLabel = $derived(sortDecl ? columnLabel(sortDecl, sortCall.args, names) : q.sort);
	const screened = $derived(data.screened !== null && data.screened < data.total);
	const noun = $derived(prettifyRoot(data.rootType));
	const span = $derived(2 + cohortCols.length + (hasStanding ? 1 : 0) + columns.length);
	const displayed = $derived.by(() => {
		const ls = localSort;
		return ls ? sortRows(pageRows, (r) => cellValue(r, ls.key), ls.asc) : pageRows;
	});
	const title = $derived(`${APP_NAME} | ${noun} table`);
	const cohortNote = $derived.by(() => {
		const parts = [`${loaded.toLocaleString()} of ${data.total.toLocaleString()} ${noun}`];
		if (q.where) parts.push(`where ${q.where}`);
		const top = screened ? ` among the top ${data.screened?.toLocaleString()} by citations` : '';
		return `${parts.join(' ')}, ranked by ${sortLabel}${top}. Click a column to sort the loaded rows.`;
	});

	function cellValue(row: TableRow, key: string) {
		return columns.some((c) => c.key === key) ? values[key]?.[row.dmId] : rowValue(row, key);
	}

	function pending(col: Column, row: TableRow) {
		return values[col.key]?.[row.dmId] === undefined && (inflight[col.key] ?? 0) > 0;
	}

	function arrow(key: string) {
		return localSort?.key === key ? (localSort.asc ? ' ↑' : ' ↓') : '';
	}

	function standing(row: TableRow): string {
		const sf = data.subfields.find((s) => s.semanticId === data.field);
		if (!data.ladder || sf?.dmId === undefined) return '';
		const cites = rowValue(row, callText('field_citations', [data.field])) ?? 0;
		const tier = citStandingTier(data.ladder.ladder[sf.dmId] ?? [], cites);
		return standingLabel(tier, tierNames) ?? '';
	}

	function go(patch: TableQuery) {
		goto(tableHref(data.rootType, { ...q, pin: data.pin, ...patch }, data.defaultSort));
	}

	function rank(metric: MetricDecl, args: MetricArgs) {
		go({ sort: callText(metric.id, args) });
	}

	function toggleLocalSort(key: string) {
		localSort = localSort?.key === key ? { key, asc: !localSort.asc } : { key, asc: false };
	}

	async function fillColumn(col: Column, rows: TableRow[]) {
		if (rows.length === 0) return;
		inflight[col.key] = (inflight[col.key] ?? 0) + 1;
		const got = await fetchColumnValues(BE_REMOTE_URL, data.rootType, rows, col);
		values = { ...values, [col.key]: { ...values[col.key], ...got.values } };
		columnError = got.error;
		inflight[col.key] -= 1;
	}

	function addColumn(metric: MetricDecl, args: MetricArgs) {
		const key = callText(metric.id, args);
		if (columns.some((c) => c.key === key) || data.columns.includes(key)) return;
		const col = { key, label: columnLabel(metric, args, names), metric, args };
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
				<span class="distinct">outside the ranked {noun}</span>
			{/if}
		</td>
		{#each cohortCols as c (c.key)}
			<td class="num">{formatMetric(c.decl, rowValue(row, c.key))}</td>
		{/each}
		{#if hasStanding}
			<td class="num standing">{standing(row)}</td>
		{/if}
		{#each columns as col (col.key)}
			<td class="num local" class:pending={pending(col, row)}>
				{pending(col, row) ? '…' : formatMetric(col.metric, values[col.key]?.[row.dmId])}
			</td>
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
		{cohortNote}
		{#if data.methodology}
			Metrics count papers {workScreenPhrase(data.methodology.workScreen)}. A column's info gives
			the years it covers.
		{/if}
	</p>
	{#if data.error || columnError}
		<p class="error">{data.error ?? columnError}</p>
	{/if}

	<div class="blocks">
		<section class="block">
			<h2>Filter</h2>
			<div class="controls">
				<ClauseBuilder
					metrics={narrowers}
					registry={data.registry}
					subfields={data.subfields}
					countries={data.countries}
					chips={data.chips}
					where={q.where ?? ''}
					{names}
					onchange={(where) => go({ where })}
				/>
			</div>
			<div class="controls">
				<EntityPins
					rootType={data.rootType}
					pins={data.pin}
					rows={data.pinned}
					onchange={(pin) => go({ pin })}
				/>
			</div>
		</section>
		<section class="block">
			<h2>Metrics</h2>
			<div class="controls">
				<span class="lead">Rank all {data.total.toLocaleString()} {noun} by</span>
				<MetricPicker
					metrics={rankings}
					subfields={data.subfields}
					countries={data.countries}
					selected={q.sort}
					action="Rank"
					onpick={rank}
				/>
			</div>
			{#if screened}
				<p class="note">
					{sortLabel} is computed per entity, so it ranks the {noun} with the most citations only: the
					top {data.screened?.toLocaleString()}.
				</p>
			{/if}
			<div class="controls">
				<span class="lead">Add a column for the loaded rows</span>
				<MetricPicker
					metrics={addable}
					subfields={data.subfields}
					countries={data.countries}
					action="Add"
					onpick={addColumn}
				/>
			</div>
		</section>
	</div>

	<div class="table-wrap">
		<table>
			<thead>
				<tr>
					<th colspan="2"></th>
					<th colspan={cohortCols.length + (hasStanding ? 1 : 0)} class="group">
						{#if screened}
							The top {data.screened?.toLocaleString()} of {data.total.toLocaleString()}
							{noun} by citations
						{:else}
							All {data.total.toLocaleString()}
							{noun}
						{/if}
					</th>
					{#if columns.length > 0}
						<th colspan={columns.length} class="group local">The loaded rows only</th>
					{/if}
				</tr>
				<tr>
					<th class="col-rank">#</th>
					<th class="col-name">Name</th>
					{#each cohortCols as c (c.key)}
						<th
							class="num sortable"
							class:ranked={q.sort === c.key}
							class:active={localSort?.key === c.key}
							aria-sort={localSort?.key === c.key
								? localSort.asc
									? 'ascending'
									: 'descending'
								: undefined}
							onclick={() => toggleLocalSort(c.key)}
						>
							<span class="head">
								{columnLabel(c.decl, c.args, names)}{arrow(c.key)}
								{#if q.sort === c.key}
									<span class="rank-mark">rank</span>
								{/if}
								<InfoTip text={c.decl.meaning} label={c.decl.label} />
							</span>
						</th>
					{/each}
					{#if hasStanding}
						<th class="num">
							<span class="head">
								Standing
								<InfoTip
									text="The most selective percentile band the entity's {fieldName} citations reach among all {noun} active in the field."
									label="Standing"
								/>
							</span>
						</th>
					{/if}
					{#each columns as col (col.key)}
						<th
							class="num sortable local"
							class:active={localSort?.key === col.key}
							onclick={() => toggleLocalSort(col.key)}
						>
							<span class="head">
								{col.label}{arrow(col.key)}
								<InfoTip
									text="{col.metric.meaning} Computed for the loaded rows only."
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
							</span>
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

	.error {
		font-size: var(--text-sm);
		color: var(--color-err);
		margin: 0 0 12px;
	}

	.blocks {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px;
	}

	@media (max-width: 900px) {
		.blocks {
			grid-template-columns: 1fr;
		}
	}

	.block {
		min-width: 0;
		border: 2px solid rgba(var(--color-range-15), 0.45);
		padding: 10px 12px;
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.block h2 {
		font-size: var(--text-xs);
		text-transform: uppercase;
		letter-spacing: 0.08em;
		opacity: 0.7;
		margin: 0;
	}

	.controls {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
		align-items: center;
	}

	.lead,
	.note {
		font-size: var(--text-sm);
		opacity: 0.7;
	}

	.note {
		margin: 0;
	}

	/* The rows scroll in this box, so the header sticks to its top edge. The reserve is the site
	   header plus the page's own content below the table: it keeps the box short enough that its top
	   edge is still on screen once the page is scrolled to its end, and with it the stuck header. */
	.table-wrap {
		overflow: auto;
		max-height: calc(100dvh - var(--header-height) - 9rem);
		margin-top: 12px;
	}

	/* Separate borders so the header's own borders travel with it while it is stuck; collapsed
	   borders belong to the table and scroll out from under a sticky row. */
	table {
		width: 100%;
		border-collapse: separate;
		border-spacing: 0;
		font-size: var(--text-base);
	}

	thead {
		position: sticky;
		top: 0;
		z-index: 2;
	}

	thead th {
		text-align: left;
		vertical-align: bottom;
		padding: 6px 8px;
		background: var(--text-bg);
		border-bottom: 2px solid rgba(var(--color-range-15), 0.15);
		font-size: var(--text-sm);
		/* Dimmed through the text color, not opacity: a stuck header has to stay opaque over the rows
		   passing under it. */
		color: color-mix(in srgb, var(--color-text) 60%, var(--text-bg));
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	/* Capped so a long label wraps onto a second line instead of stretching its column far past the
	   numbers under it. */
	.head {
		display: inline-block;
		max-width: 13em;
		white-space: normal;
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
	thead th.active,
	thead th.ranked {
		color: var(--color-text);
	}

	.rank-mark {
		font-size: var(--text-xs);
		letter-spacing: 0;
		text-transform: none;
		border: 1px solid currentColor;
		border-radius: 3px;
		padding: 0 4px;
		margin-left: 4px;
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

	tbody td {
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
		font-variant-numeric: tabular-nums;
	}

	td.col-rank {
		opacity: 0.35;
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

	td.pending {
		opacity: 0.35;
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
