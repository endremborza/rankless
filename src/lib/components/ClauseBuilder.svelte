<script lang="ts">
	import ParamInputs from './ParamInputs.svelte';
	import {
		callText,
		chipLabel,
		clauseText,
		isNumeric,
		isSet,
		opLabel,
		operatorsFor,
		whereText,
		type Chip,
		type MetricArgs,
		type Names
	} from '$lib/table-utils';
	import type { MetricDecl, SearchResult, WhereOp } from '$lib/tree-types';

	// Narrows the cohort with one clause at a time: a metric call, an operator its value type
	// allows, and an operand, each active clause a chip. A `where` the chips cannot show (anything
	// but a conjunction of clauses) is edited as text.
	let {
		metrics,
		registry,
		subfields,
		countries,
		chips,
		where,
		names,
		onchange
	}: {
		metrics: MetricDecl[];
		registry: MetricDecl[];
		subfields: SearchResult[];
		countries: SearchResult[];
		chips: Chip[] | null;
		where: string;
		names: Names;
		onchange: (where: string) => void;
	} = $props();

	let metricId = $state('');
	let args = $state<MetricArgs>([]);
	let op = $state<WhereOp>('ge');
	let operand = $state<string | number | null>(null);
	let text = $derived(where);
	const decl = $derived(metrics.find((m) => m.id === metricId));
	const entity = $derived(decl && !isNumeric(decl) ? decl.value : null);

	function choose(id: string) {
		metricId = id;
		const d = metrics.find((m) => m.id === id);
		args = [];
		operand = null;
		op = d && isNumeric(d) ? 'ge' : 'eq';
	}

	function add() {
		if (!decl || !isSet(operand)) return;
		if (decl.param && !args.every(isSet)) return;
		const chip: Chip = { call: callText(decl.id, args), op, operand };
		const rest = chips ?? [];
		onchange(whereText([...rest, chip]));
		choose('');
	}

	function remove(i: number) {
		if (!chips) return;
		onchange(whereText(chips.filter((_, j) => j !== i)));
	}
</script>

{#if chips === null}
	<input
		class="control expression"
		type="text"
		aria-label="Narrowing expression"
		bind:value={text}
	/>
	<button class="control" type="button" onclick={() => onchange(text)}>Apply</button>
{:else}
	<select
		class="control"
		class:placeholder={!metricId}
		aria-label="Narrow by a metric"
		value={metricId}
		onchange={(e) => choose(e.currentTarget.value)}
	>
		<option value="">Narrow by…</option>
		{#each metrics as m, i (i)}
			<option value={m.id}>{m.label}</option>
		{/each}
	</select>
	{#if decl}
		{#if decl.param}
			<ParamInputs {decl} {subfields} {countries} bind:args />
		{/if}
		<select class="control" aria-label="Operator" bind:value={op}>
			{#each operatorsFor(decl) as o (o)}
				<option value={o}>{opLabel(o)}</option>
			{/each}
		</select>
		{#if entity?.type === 'entity' || entity?.type === 'entities'}
			{#if entity.entity === 'countries'}
				<select
					class="control"
					class:placeholder={!operand}
					aria-label="Value"
					value={operand ?? ''}
					onchange={(e) => (operand = e.currentTarget.value)}
				>
					<option value="">Country…</option>
					{#each countries as c, i (i)}
						<option value={c.semanticId}>{c.name}</option>
					{/each}
				</select>
			{:else}
				<input
					class="control"
					type="text"
					aria-label="Value"
					placeholder="Name…"
					value={operand ?? ''}
					oninput={(e) => (operand = e.currentTarget.value)}
				/>
			{/if}
		{:else}
			<input
				class="control bound"
				type="number"
				aria-label="Value"
				placeholder="value"
				value={operand ?? ''}
				oninput={(e) =>
					(operand = e.currentTarget.value === '' ? null : e.currentTarget.valueAsNumber)}
			/>
		{/if}
		<button class="control" type="button" onclick={add}>Narrow</button>
	{/if}
	{#each chips as chip, i (clauseText(chip))}
		<span class="chip">
			{chipLabel(chip, registry, names)}
			<button
				type="button"
				aria-label="Drop {chipLabel(chip, registry, names)}"
				onclick={() => remove(i)}>×</button
			>
		</span>
	{/each}
{/if}

<style>
	.bound {
		width: 7em;
	}

	.expression {
		flex: 1;
		min-width: 240px;
		font-family: monospace;
	}
</style>
