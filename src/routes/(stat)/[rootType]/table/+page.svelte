<script lang="ts">
	import { untrack } from 'svelte';
	import { APP_NAME, BE_REMOTE_URL } from '$lib/constants';
	import { prettifyRoot } from '$lib/text-format-util';
	import type { SearchResult, RootType } from '$lib/tree-types';

	let {
		data
	}: {
		data: {
			rootType: RootType;
			rows: SearchResult[];
			from: number;
			hasMore: boolean;
			pageSize: number;
		};
	} = $props();

	let searchQuery = $state('');
	let sortCol = $state<'name' | 'papers' | 'citations'>('citations');
	let sortAsc = $state(false);
	let extraRows = $state<SearchResult[]>([]);
	let loadingMore = $state(false);
	// Pagination state is seeded from the initial load, then mutated by loadMore (not reset on
	// data changes — matches the pre-runes behavior); untrack marks the read as intentional.
	let noMore = $state(untrack(() => !data.hasMore));
	let currentFrom = $state(untrack(() => data.from + data.rows.length));

	const allRows = $derived([...data.rows, ...extraRows]);

	const filtered = $derived(
		searchQuery.trim()
			? allRows.filter((r) => r.name.toLowerCase().includes(searchQuery.trim().toLowerCase()))
			: allRows
	);

	const sorted = $derived(
		[...filtered].sort((a, b) => {
			let cmp = 0;
			if (sortCol === 'name') cmp = a.name.localeCompare(b.name);
			else if (sortCol === 'papers') cmp = a.papers - b.papers;
			else cmp = a.citations - b.citations;
			return sortAsc ? cmp : -cmp;
		})
	);

	function toggleSort(col: typeof sortCol) {
		if (sortCol === col) sortAsc = !sortAsc;
		else {
			sortCol = col;
			sortAsc = col === 'name';
		}
	}

	function sortIndicator(col: typeof sortCol) {
		if (sortCol !== col) return '';
		return sortAsc ? ' ↑' : ' ↓';
	}

	async function loadMore() {
		if (loadingMore || noMore) return;
		loadingMore = true;
		const rows: SearchResult[] = await fetch(
			`${BE_REMOTE_URL}/slice/${data.rootType}/${currentFrom}/${currentFrom + data.pageSize}`
		)
			.then((r) => (r.ok ? r.json() : []))
			.catch(() => []);
		extraRows = [...extraRows, ...rows];
		currentFrom += rows.length;
		if (rows.length < data.pageSize) noMore = true;
		loadingMore = false;
	}

	const title = $derived(`${APP_NAME} | ${prettifyRoot(data.rootType)} table`);
	const entityUrl = (r: SearchResult) => `/${data.rootType}/${r.semanticId}`;
</script>

<svelte:head>
	<title>{title}</title>
</svelte:head>

<div class="table-page shadowy padded marged">
	<div class="table-header">
		<div class="table-title">
			<h1>{prettifyRoot(data.rootType)}</h1>
		</div>
		<input
			type="search"
			bind:value={searchQuery}
			placeholder="Filter by name…"
			class="search-input"
		/>
	</div>

	<div class="table-wrap">
		<table>
			<thead>
				<tr>
					<th class="col-rank">#</th>
					<th class="col-name sortable" onclick={() => toggleSort('name')}>
						Name{sortIndicator('name')}
					</th>
					<th class="col-papers sortable" onclick={() => toggleSort('papers')}>
						Papers{sortIndicator('papers')}
					</th>
					<th class="col-citations sortable" onclick={() => toggleSort('citations')}>
						Citations{sortIndicator('citations')}
					</th>
				</tr>
			</thead>
			<tbody>
				{#each sorted as row, i (i)}
					<tr>
						<td class="col-rank">{data.from + i + 1}</td>
						<td class="col-name">
							<a href={entityUrl(row)}>{@html row.name}</a>
							{#if row.distinctText}
								<span class="distinct">{row.distinctText}</span>
							{/if}
						</td>
						<td class="col-papers">{row.papers.toLocaleString()}</td>
						<td class="col-citations">{row.citations.toLocaleString()}</td>
					</tr>
				{/each}
				{#if sorted.length === 0}
					<tr>
						<td colspan="4" class="empty">No results for "{searchQuery}"</td>
					</tr>
				{/if}
			</tbody>
		</table>
	</div>

	{#if !noMore && !searchQuery}
		<button class="load-more" onclick={loadMore} disabled={loadingMore}>
			{loadingMore ? 'Loading…' : `Load more (showing ${allRows.length})`}
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
		gap: 16px;
		flex-wrap: wrap;
		margin-bottom: 16px;
	}

	.table-title {
		display: flex;
		align-items: baseline;
		gap: 12px;
	}

	.table-title h1 {
		margin: 0;
		text-transform: capitalize;
	}

	.search-input {
		flex: 1;
		max-width: 320px;
		padding: 6px 10px;
		font-size: var(--text-base);
		font-family: inherit;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		background: transparent;
		color: var(--color-text);
	}

	.search-input:focus {
		outline: none;
		border-color: rgba(var(--color-range-15), 0.4);
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

	thead th.sortable:hover {
		opacity: 1;
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

	.col-papers,
	.col-citations {
		text-align: right;
		font-variant-numeric: tabular-nums;
		width: 100px;
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
