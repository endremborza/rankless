<script lang="ts">
	import { page } from '$app/state';
	import ParamInputs from './ParamInputs.svelte';
	import { argsReady, callText, defaultArgs, parseCall, type MetricArgs } from '$lib/table-utils';
	import type { MetricDecl, NamedEntity } from '$lib/tree-types';

	// Picks a metric and the argument its parameter takes, and hands over the call. A pick that
	// asks for nothing applies at once, one with a parameter applies with the button. `selected`
	// is the call the picker mirrors (the active ranking), empty for a one-off pick.
	let {
		metrics,
		subfields,
		countries,
		selected = '',
		action,
		onpick
	}: {
		metrics: MetricDecl[];
		subfields: NamedEntity[];
		countries: NamedEntity[];
		selected?: string;
		action: string;
		onpick: (metric: MetricDecl, args: MetricArgs) => void;
	} = $props();

	let picked = $state<string | null>(null);
	const current = $derived(parseCall(selected));
	// The mirrored call's arguments until a choice overrides them; a new `selected` resets both.
	let args = $derived<MetricArgs>(current.args);
	const metricId = $derived(picked ?? current.metric);
	const decl = $derived(metrics.find((m) => m.id === metricId));

	// The metric and its arguments are read before the choice is reset: the reset moves `decl`
	// back to `selected`.
	function pick() {
		const d = decl;
		const chosen = args;
		if (!d || !argsReady(d, chosen)) return;
		picked = null;
		if (callText(d.id, chosen) !== selected) onpick(d, chosen);
	}

	function choose(id: string) {
		picked = id;
		const d = metrics.find((m) => m.id === id);
		const base = id === current.metric ? current.args : [];
		args = d ? defaultArgs(d, base, page.data.methodology?.yearlyCounts) : [];
		if (d && !d.param) pick();
	}
</script>

<div class="picker">
	<select
		class="control"
		class:placeholder={!metricId}
		aria-label={action}
		value={metricId}
		onchange={(e) => choose(e.currentTarget.value)}
	>
		<option value="">Metric…</option>
		{#each metrics as m, i (i)}
			<option value={m.id}>{m.label}</option>
		{/each}
	</select>
	{#if decl?.param}
		<ParamInputs {decl} {subfields} {countries} bind:args />
		<button class="control" type="button" onclick={pick}>{action}</button>
	{/if}
	{#if decl}
		<span class="note">{decl.meaning}</span>
	{/if}
</div>

<style>
	.picker {
		flex: 1 1 100%;
		min-width: 0;
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
		align-items: center;
	}

	.note {
		flex-basis: 100%;
		font-size: var(--text-sm);
		opacity: 0.6;
	}
</style>
