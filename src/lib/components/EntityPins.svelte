<script lang="ts">
	import PeerSearch from './PeerSearch.svelte';
	import { prettifyRoot } from '$lib/text-format-util';
	import type { RootType, SearchResult, TableRow } from '$lib/tree-types';

	// Entities kept on the table whatever its ordering and filter: a name search adds one, a chip
	// removes it, and the pinned rows name the chips.
	export let rootType: RootType;
	export let pins: string[];
	export let rows: TableRow[];
	export let onchange: (pins: string[]) => void;

	$: nameOf = (sem: string) => rows.find((r) => r.semanticId === sem)?.name ?? sem;

	function add(e: CustomEvent<SearchResult>) {
		const sem = e.detail.semanticId;
		if (!pins.includes(sem)) onchange([...pins, sem]);
	}
</script>

<div class="pins">
	<PeerSearch {rootType} placeholder="Pin {prettifyRoot(rootType)} by name…" on:select={add} />
	{#each pins as sem, i (i)}
		<span class="chip">
			{@html nameOf(sem)}
			<button
				type="button"
				aria-label="Unpin {nameOf(sem)}"
				on:click={() => onchange(pins.filter((p) => p !== sem))}>×</button
			>
		</span>
	{/each}
</div>

<style>
	.pins {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
		align-items: center;
		flex: 1;
		min-width: 240px;
	}
</style>
