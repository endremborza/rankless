<script lang="ts">
	import { BE_REMOTE_URL, LATEST_YEAR } from '$lib/constants';
	import {
		columnKey,
		columnLabel,
		isSet,
		sliceList,
		type IntricateColumn,
		type MetricParams
	} from '$lib/table-utils';
	import type { MetricDecl, SearchResult } from '$lib/tree-types';

	// Picks an intricate metric and its parameters, and hands over the page-local column they make.
	let {
		metrics,
		subfields,
		onadd
	}: { metrics: MetricDecl[]; subfields: SearchResult[]; onadd: (col: IntricateColumn) => void } =
		$props();

	let metricId = $state('');
	let params = $state<MetricParams>({
		year_from: LATEST_YEAR - 5,
		year_to: LATEST_YEAR,
		subfield: '',
		country: ''
	});
	let countries = $state<SearchResult[]>([]);
	let countriesRequested = false;
	const decl = $derived(metrics.find((m) => m.id === metricId));

	$effect(() => {
		if (decl?.params.includes('country') && !countriesRequested) {
			countriesRequested = true;
			sliceList(BE_REMOTE_URL, 'countries', 400).then((c) => (countries = c));
		}
	});

	function add() {
		if (!decl) return;
		const chosen: MetricParams = {};
		for (const p of decl.params) {
			const v = params[p as keyof MetricParams];
			if (!isSet(v)) return;
			(chosen as Record<string, string | number>)[p] = v;
		}
		const names = {
			subfield: subfields.find((s) => s.semanticId === chosen.subfield)?.name,
			country: countries.find((c) => c.semanticId === chosen.country)?.name
		};
		onadd({
			key: columnKey(decl.id, chosen),
			label: columnLabel(decl, chosen, names),
			metric: decl,
			params: chosen
		});
	}
</script>

<div class="adder">
	<select class="control" aria-label="Add a page-local column" bind:value={metricId}>
		<option value="">Add a column for the loaded rows…</option>
		{#each metrics as m, i (i)}
			<option value={m.id}>{m.label}</option>
		{/each}
	</select>
	{#if decl}
		{#each decl.params as p, i (i)}
			{#if p === 'subfield'}
				<select class="control" aria-label="Field" bind:value={params.subfield}>
					<option value="">Field…</option>
					{#each subfields as sf, j (j)}
						<option value={sf.semanticId}>{sf.name}</option>
					{/each}
				</select>
			{:else if p === 'country'}
				<select class="control" aria-label="Country" bind:value={params.country}>
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
					bind:value={params.year_from}
				/>
			{:else if p === 'year_to'}
				<input
					class="control year"
					type="number"
					aria-label="To year"
					bind:value={params.year_to}
				/>
			{/if}
		{/each}
		<button class="control" type="button" onclick={add}>Add</button>
		<span class="note">{decl.meaning}</span>
	{/if}
</div>

<style>
	.adder {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
		align-items: center;
	}

	.year {
		width: 6em;
	}

	.note {
		font-size: var(--text-sm);
		opacity: 0.6;
	}
</style>
