<script lang="ts">
	import { page } from '$app/state';
	import type { MetricDecl, NamedEntity } from '$lib/tree-types';

	// The inputs of a metric's parameter: a field, a country, or a year window; `args` is what the
	// call is made with.
	let {
		decl,
		subfields,
		countries,
		args = $bindable()
	}: {
		decl: MetricDecl;
		subfields: NamedEntity[];
		countries: NamedEntity[];
		args: (string | number)[];
	} = $props();

	// The years a window can name; the backend refuses any other, so the inputs bound and flag them.
	const yearly = $derived(page.data.methodology?.yearlyCounts);

	function setYear(i: number, v: number) {
		const next = [...args];
		next[i] = Number.isNaN(v) ? '' : v;
		args = next;
	}
</script>

{#if decl.param === 'subfield'}
	<select
		class="control"
		class:placeholder={!args[0]}
		aria-label="Field"
		value={args[0] ?? ''}
		onchange={(e) => (args = [e.currentTarget.value])}
	>
		<option value="">Field…</option>
		{#each subfields as sf, i (i)}
			<option value={sf.semanticId}>{sf.name}</option>
		{/each}
	</select>
{:else if decl.param === 'country'}
	<select
		class="control"
		class:placeholder={!args[0]}
		aria-label="Country"
		value={args[0] ?? ''}
		onchange={(e) => (args = [e.currentTarget.value])}
	>
		<option value="">Country…</option>
		{#each countries as c, i (i)}
			<option value={c.semanticId}>{c.name}</option>
		{/each}
	</select>
{:else if decl.param === 'window'}
	<input
		class="control year"
		type="number"
		aria-label="From year"
		min={yearly?.[0]}
		max={args[1] || yearly?.[1]}
		value={args[0] ?? ''}
		onchange={(e) => setYear(0, e.currentTarget.valueAsNumber)}
	/>
	<input
		class="control year"
		type="number"
		aria-label="To year"
		min={args[0] || yearly?.[0]}
		max={yearly?.[1]}
		value={args[1] ?? ''}
		onchange={(e) => setYear(1, e.currentTarget.valueAsNumber)}
	/>
{/if}

<style>
	.year {
		width: 6em;
	}

	.year:invalid {
		outline: 1px solid var(--color-err);
	}
</style>
