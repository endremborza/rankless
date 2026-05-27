<script lang="ts">
	import { BE_REMOTE_URL } from '$lib/constants';
	import { formatNumber } from '$lib/text-format-util';
	import type { SearchResult } from '$lib/tree-types';
	import { createEventDispatcher } from 'svelte';

	export let rootType: string;
	export let placeholder = 'Search…';
	export let excludeSemanticId: string | undefined = undefined;

	const dispatch = createEventDispatcher<{ select: SearchResult }>();

	let term = '';
	let results: SearchResult[] = [];
	let open = false;
	let latestTerm = '';
	let timer: ReturnType<typeof setTimeout> | undefined;

	async function run(q: string) {
		latestTerm = q;
		if (!q.trim()) {
			results = [];
			open = false;
			return;
		}
		try {
			const res = await fetch(
				`${BE_REMOTE_URL}/names/${rootType}?` + new URLSearchParams({ q }).toString()
			);
			const l: SearchResult[] = await res.json();
			if (latestTerm !== q) return;
			results = l.filter((e) => e.semanticId !== excludeSemanticId);
			open = true;
		} catch (e) {
			console.error('peer search failed', e);
		}
	}

	function onInput() {
		clearTimeout(timer);
		timer = setTimeout(() => run(term), 200);
	}

	function choose(r: SearchResult) {
		dispatch('select', r);
		term = '';
		results = [];
		open = false;
	}
</script>

<div class="peer-search">
	<input
		type="text"
		bind:value={term}
		on:input={onInput}
		on:focus={() => (open = results.length > 0)}
		on:blur={() => setTimeout(() => (open = false), 120)}
		{placeholder}
	/>
	{#if open && results.length > 0}
		<ul class="ps-results">
			{#each results as r}
				<li>
					<button type="button" on:mousedown|preventDefault={() => choose(r)}>
						<span class="ps-name">{@html r.name}</span>
						<span class="ps-meta"
							>{formatNumber(r.papers)} papers · {formatNumber(r.citations)} cites</span
						>
					</button>
				</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	.peer-search {
		position: relative;
		min-width: 0;
		flex: 1;
	}

	input {
		width: 100%;
		box-sizing: border-box;
		padding: 5px 8px;
		font-size: var(--text-sm);
		color: inherit;
		background: var(--text-bg, #fff);
		border: 1px solid rgba(var(--color-range-30), 0.35);
	}

	input:focus {
		outline: none;
		border-color: rgba(var(--color-range-15), 0.8);
	}

	.ps-results {
		position: absolute;
		z-index: 20;
		top: calc(100% + 4px);
		left: 0;
		right: 0;
		margin: 0;
		padding: 4px;
		list-style: none;
		max-height: 280px;
		overflow-y: auto;
		background: var(--text-bg, #fff);
		border: 1px solid rgba(var(--color-range-30), 0.35);
		box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
	}

	.ps-results button {
		display: flex;
		flex-direction: column;
		gap: 1px;
		width: 100%;
		padding: 5px 7px;
		text-align: left;
		background: none;
		border: none;
		cursor: pointer;
		color: inherit;
	}

	.ps-results button:hover {
		background: rgba(var(--color-range-15), 0.08);
	}

	.ps-name {
		font-size: var(--text-sm);
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.ps-meta {
		font-size: var(--text-xs);
		font-variant-numeric: tabular-nums;
		opacity: 0.55;
	}
</style>
