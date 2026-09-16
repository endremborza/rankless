<script lang="ts">
	import { untrack } from 'svelte';
	import { goto } from '$app/navigation';
	import { APP_NAME, BE_REMOTE_URL, LATEST_YEAR } from '$lib/constants';
	import { prettifyRoot } from '$lib/text-format-util';
	import { entToLink } from '$lib/tree-functions';
	import { citStandingTier, standingLabel, tierLabels } from '$lib/peers-utils';
	import {
		columnKey,
		fieldFilterable,
		formatMetric,
		globalColumns,
		isSet,
		metricValuesUrl,
		metricsFor,
		rowValue,
		sliceList,
		sliceUrl,
		sortRows,
		tableHref,
		type IntricateColumn,
		type MetricParams
	} from '$lib/table-utils';
	import InfoTip from '$lib/components/InfoTip.svelte';
	import type {
		LadderData,
		MetricDecl,
		MetricValuesResp,
		RootType,
		SearchResult,
		TableRow
	} from '$lib/tree-types';

	let {
		data
	}: {
		data: {
			rootType: RootType;
			rows: TableRow[];
			from: number;
			total: number;
			pageSize: number;
			sort: string;
			subfield: string;
			q: string;
			registry: MetricDecl[];
			subfields: SearchResult[];
			ladder: LadderData | null;
		};
	} = $props();

	type PageExtension = { of: TableRow[]; rows: TableRow[]; done: boolean };

	let loadingMore = $state(false);
	// Rows loaded past the server-rendered page, tied to the page they extend: a sort, field or
	// search change loads new data into this same component instance, and a render with the new
	// rows drops the old extension before it can collide with them. untrack marks the seed read.
	let extra = $state.raw<PageExtension>({ of: untrack(() => data.rows), rows: [], done: false });
	let nameQuery = $state(untrack(() => data.q));

	// Page-local columns: intricate metrics evaluated for the rows on screen, one call per column
	// per loaded page, never one per row. Values are keyed by column then by dm id.
	let columns = $state<IntricateColumn[]>([]);
	let values = $state<Record<string, Record<number, number | null>>>({});
	let loadingColumns = $state(0);
	let localSort = $state<{ key: string; asc: boolean } | null>(null);
	let pendingMetric = $state('');
	let pendingParams = $state<MetricParams>({
		year_from: LATEST_YEAR - 5,
		year_to: LATEST_YEAR,
		subfield: '',
		country: ''
	});
	let countries = $state<SearchResult[]>([]);

	// The rest of the per-page state follows a new load after its render.
	$effect(() => {
		const { rows, q } = data;
		untrack(() => {
			nameQuery = q;
			localSort = null;
			columns.forEach((c) => fetchColumn(c, rows));
		});
	});

	const extension = $derived(
		extra.of === data.rows ? extra : { of: data.rows, rows: [], done: false }
	);
	const allRows = $derived([...data.rows, ...extension.rows]);
	const noMore = $derived(data.q !== '' || extension.done || data.rows.length < data.pageSize);
	const hasField = $derived(data.subfield !== '');
	const globals = $derived(globalColumns(data.registry, data.rootType, hasField));
	const intricates = $derived(metricsFor(data.registry, data.rootType, 'intricate'));
	const narrowable = $derived(fieldFilterable(data.registry, data.rootType));
	const field = $derived(data.subfields.find((s) => s.semanticId === data.subfield));
	const tierNames = $derived(data.ladder ? tierLabels(data.ladder.pctBands) : []);
	const pendingDecl = $derived(intricates.find((m) => m.id === pendingMetric));

	const displayed = $derived(
		localSort ? sortRows(allRows, (r) => values[localSort!.key]?.[r.dmId], localSort.asc) : allRows
	);

	function standing(row: TableRow): string | null {
		if (!data.ladder || field?.dmId === undefined) return null;
		const tier = citStandingTier(data.ladder.ladder[field.dmId] ?? [], row.fieldCitations ?? 0);
		return standingLabel(tier, tierNames);
	}

	function sortBy(metricId: string) {
		localSort = null;
		goto(tableHref(data.rootType, { sort: metricId, subfield: data.subfield, q: data.q }));
	}

	function setSubfield(e: Event) {
		const subfield = (e.currentTarget as HTMLSelectElement).value;
		goto(tableHref(data.rootType, { sort: data.sort, subfield, q: data.q }));
	}

	function submitName(e: SubmitEvent) {
		e.preventDefault();
		goto(tableHref(data.rootType, { sort: data.sort, subfield: data.subfield, q: nameQuery }));
	}

	function toggleLocalSort(key: string) {
		localSort = localSort?.key === key ? { key, asc: !localSort.asc } : { key, asc: false };
	}

	async function fetchColumn(col: IntricateColumn, rows: TableRow[]) {
		if (rows.length === 0) return;
		loadingColumns += 1;
		try {
			const ids = rows.map((r) => r.dmId);
			const resp: MetricValuesResp | null = await fetch(
				metricValuesUrl(BE_REMOTE_URL, data.rootType, ids, col.metric.id, col.params)
			)
				.then((r) => (r.ok ? r.json() : null))
				.catch(() => null);
			const got: Record<number, number | null> = { ...(values[col.key] ?? {}) };
			resp?.ids.forEach((id, i) => (got[id] = resp.values[col.metric.id]?.[i] ?? null));
			values = { ...values, [col.key]: got };
		} finally {
			loadingColumns -= 1;
		}
	}

	async function addColumn() {
		if (!pendingDecl) return;
		const params: MetricParams = {};
		for (const p of pendingDecl.params) {
			const v = pendingParams[p as keyof MetricParams];
			if (!isSet(v)) return;
			(params as Record<string, string | number>)[p] = v;
		}
		const key = columnKey(pendingDecl.id, params);
		if (columns.some((c) => c.key === key)) return;
		const col = { key, metric: pendingDecl, params };
		columns = [...columns, col];
		await fetchColumn(col, allRows);
	}

	function removeColumn(key: string) {
		columns = columns.filter((c) => c.key !== key);
		if (localSort?.key === key) localSort = null;
	}

	async function loadCountries() {
		if (countries.length > 0) return;
		countries = await sliceList(BE_REMOTE_URL, 'countries', 400);
	}

	$effect(() => {
		if (pendingDecl?.params.includes('country')) loadCountries();
	});

	async function loadMore() {
		if (loadingMore || noMore) return;
		loadingMore = true;
		const of = data.rows;
		const rows: TableRow[] = await fetch(
			sliceUrl(BE_REMOTE_URL, data.rootType, data.from + allRows.length, {
				sort: data.sort,
				subfield: data.subfield
			})
		)
			.then((r) => (r.ok ? r.json() : []))
			.catch(() => []);
		loadingMore = false;
		if (of !== data.rows) return;
		extra = { of, rows: [...extension.rows, ...rows], done: rows.length < data.pageSize };
		await Promise.all(columns.map((c) => fetchColumn(c, rows)));
	}

	const title = $derived(`${APP_NAME} | ${prettifyRoot(data.rootType)} table`);
	const rowLink = (r: TableRow) => entToLink({ rootType: data.rootType, semanticId: r.semanticId });
	const sortLabel = $derived(
		data.registry.find((m) => m.id === data.sort)?.label.toLowerCase() ?? data.sort
	);
</script>

<svelte:head>
	<title>{title}</title>
</svelte:head>

<div class="table-page shadowy padded marged">
	<div class="table-header">
		<div class="table-title">
			<h1>{prettifyRoot(data.rootType)}</h1>
			<span class="cohort-note">
				{#if data.q}
					name matches ranked by {sortLabel}
				{:else}
					{allRows.length.toLocaleString()} of {data.total.toLocaleString()} ranked by {sortLabel}
				{/if}
				{#if field}in {field.name}{/if}
			</span>
		</div>
		<form class="controls" onsubmit={submitName}>
			<input
				type="search"
				name="q"
				bind:value={nameQuery}
				placeholder="Search by name…"
				aria-label="Search by name"
				class="control"
			/>
			{#if narrowable}
				<select
					class="control"
					aria-label="Narrow to a field"
					value={data.subfield}
					onchange={setSubfield}
				>
					<option value="">All fields</option>
					{#each data.subfields as sf, i (i)}
						<option value={sf.semanticId}>{sf.name}</option>
					{/each}
				</select>
			{/if}
		</form>
	</div>

	<div class="add-column">
		<select class="control" aria-label="Add a page-local column" bind:value={pendingMetric}>
			<option value="">Add a column for this page…</option>
			{#each intricates as m, i (i)}
				<option value={m.id}>{m.label}</option>
			{/each}
		</select>
		{#if pendingDecl}
			{#each pendingDecl.params as p, i (i)}
				{#if p === 'subfield'}
					<select class="control" aria-label="Field" bind:value={pendingParams.subfield}>
						<option value="">Field…</option>
						{#each data.subfields as sf, j (j)}
							<option value={sf.semanticId}>{sf.name}</option>
						{/each}
					</select>
				{:else if p === 'country'}
					<select class="control" aria-label="Country" bind:value={pendingParams.country}>
						<option value="">Country…</option>
						{#each countries as c, j (j)}
							<option value={c.semanticId}>{c.name}</option>
						{/each}
					</select>
				{:else if p === 'year_from'}
					<input
						class="control year"
						type="number"
						aria-label="From year"
						bind:value={pendingParams.year_from}
					/>
				{:else if p === 'year_to'}
					<input
						class="control year"
						type="number"
						aria-label="To year"
						bind:value={pendingParams.year_to}
					/>
				{/if}
			{/each}
			<button class="control" type="button" onclick={addColumn}>Add</button>
			<span class="note">{pendingDecl.meaning} Computed for the loaded rows only.</span>
		{/if}
	</div>

	<div class="table-wrap">
		<table>
			<thead>
				<tr>
					<th class="col-rank">#</th>
					<th class="col-name">Name</th>
					{#each globals as m (m.id)}
						<th
							class="num sortable"
							class:active={data.sort === m.id}
							onclick={() => sortBy(m.id)}
							title="Sort the whole cohort by {m.label.toLowerCase()}"
						>
							{m.label}{data.sort === m.id ? ' ↓' : ''}
							<InfoTip text={m.meaning} label={m.label} />
						</th>
					{/each}
					{#if hasField && data.ladder}
						<th class="num">Standing</th>
					{/if}
					{#each columns as col (col.key)}
						<th
							class="num sortable local"
							class:active={localSort?.key === col.key}
							onclick={() => toggleLocalSort(col.key)}
							title="Sorts the loaded rows only; the cohort keeps its {sortLabel} order"
						>
							{col.metric.label}
							<span class="page-local">this page</span>
							{localSort?.key === col.key ? (localSort.asc ? ' ↑' : ' ↓') : ''}
							<InfoTip
								text="{col.metric
									.meaning} Computed for the loaded rows only; sorting here reorders this page, not the cohort."
								label={col.metric.label}
							/>
							<button
								class="remove"
								type="button"
								aria-label="Remove column {col.metric.label}"
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
				{#each displayed as row (row.dmId)}
					<tr>
						<td class="col-rank">{row.rank.toLocaleString()}</td>
						<td class="col-name">
							<a href={rowLink(row)}>{@html row.name}</a>
							{#if row.distinctText}
								<span class="distinct">{row.distinctText}</span>
							{/if}
						</td>
						{#each globals as m (m.id)}
							<td class="num">{formatMetric(m.id, rowValue(row, m.id))}</td>
						{/each}
						{#if hasField && data.ladder}
							<td class="num standing">{standing(row) ?? ''}</td>
						{/if}
						{#each columns as col (col.key)}
							<td class="num local">
								{formatMetric(col.metric.id, values[col.key]?.[row.dmId])}
							</td>
						{/each}
					</tr>
				{/each}
				{#if displayed.length === 0}
					<tr>
						<td colspan={2 + globals.length + columns.length} class="empty">
							{#if data.q}No name matches "{data.q}"{:else}No entities in this cohort{/if}
						</td>
					</tr>
				{/if}
			</tbody>
		</table>
	</div>

	{#if loadingColumns > 0}
		<p class="note">Computing page-local columns…</p>
	{/if}

	{#if !noMore}
		<button class="load-more" onclick={loadMore} disabled={loadingMore}>
			{loadingMore ? 'Loading…' : `Load more (showing ${allRows.length.toLocaleString()})`}
		</button>
	{/if}
</div>

<style>
	.table-page {
		margin-top: var(--unified-margin);
		margin-bottom: var(--unified-margin);
	}

	.table-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		flex-wrap: wrap;
		margin-bottom: 12px;
	}

	.table-title {
		display: flex;
		align-items: baseline;
		gap: 12px;
		flex-wrap: wrap;
	}

	.table-title h1 {
		margin: 0;
		text-transform: capitalize;
	}

	.cohort-note,
	.note {
		font-size: var(--text-sm);
		opacity: 0.6;
	}

	.controls,
	.add-column {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
		align-items: center;
	}

	.add-column {
		margin-bottom: 12px;
	}

	.control {
		padding: 6px 10px;
		font-size: var(--text-base);
		font-family: inherit;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		background: transparent;
		color: var(--color-text);
		max-width: 100%;
	}

	.control.year {
		width: 6em;
	}

	.control:focus {
		outline: none;
		border-color: rgba(var(--color-range-15), 0.4);
	}

	button.control {
		cursor: pointer;
	}

	.table-wrap {
		overflow-x: auto;
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

	thead th.sortable {
		cursor: pointer;
		user-select: none;
	}

	thead th.sortable:hover,
	thead th.active {
		opacity: 1;
	}

	.page-local {
		display: inline-block;
		font-size: var(--text-xs);
		text-transform: none;
		letter-spacing: 0;
		padding: 0 4px;
		margin-left: 4px;
		border: 1px solid rgba(var(--color-range-15), 0.3);
		border-radius: 3px;
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
		transition: background 0.1s;
	}

	tbody tr:hover {
		background: rgba(var(--color-range-15), 0.04);
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
