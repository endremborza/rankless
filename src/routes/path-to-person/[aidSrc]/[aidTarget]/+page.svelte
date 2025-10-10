<script lang="ts">
	import type * as tt from '$lib/tree-types';
	import { BE_REMOTE_URL } from '$lib/constants';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import type { SearchResult } from '$lib/tree-types';
	import RefTreeTable from '$lib/components/RefTreeTable.svelte';

	export let data: { srcAid: string; targetAid: string };

	let srcAid = data.srcAid;
	let targetAid = data.targetAid;
	const emptyResp = {
		paths: [],
		doiMap: {},
		nameMap: {},
		relWorks: [],
		srcName: '',
		targetName: ''
	};
	let hits: tt.PathResp = emptyResp;

	let srcResults: SearchResult[] = [];
	let targetResults: SearchResult[] = [];
	let srcFocused = false;
	let targetFocused = false;

	onMount(() => {
		reloadPaths();
	});

	async function reloadPaths() {
		if (!srcAid || !targetAid || srcAid === 'src' || targetAid === 'target') return;
		goto(`/path-to-person/${srcAid}/${targetAid}`, { replaceState: true, noScroll: true });
		const beBase = BE_REMOTE_URL;
		const paToPeUrl = `${beBase}/path-to-paper/${srcAid}/${targetAid}/true`;
		try {
			hits = await fetch(paToPeUrl).then((r) => r.json());
		} catch (e) {
			console.error(e);
			hits = emptyResp;
		}
	}

	async function fetchResults(term: string, type: 'src' | 'target') {
		if (!term) return;
		const res = await fetch(`${BE_REMOTE_URL}/names/authors?q=${encodeURIComponent(term)}`);
		const list: SearchResult[] = await res.json();
		if (type === 'src') srcResults = list.slice(0, 8);
		else targetResults = list.slice(0, 8);
	}

	function selectResult(r: SearchResult, type: 'src' | 'target') {
		if (type === 'src') {
			srcAid = r.semanticId;
			srcResults = [];
			srcFocused = false;
		} else {
			targetAid = r.semanticId;
			targetResults = [];
			targetFocused = false;
		}
		reloadPaths();
	}
</script>

<div class="container">
	<div class="control">
		<div class="autocomplete">
			<input
				type="text"
				placeholder="Source author"
				bind:value={srcAid}
				on:focus={() => (srcFocused = true)}
				on:input={(e) => fetchResults(e.target.value, 'src')}
				on:blur={() => setTimeout(() => (srcFocused = false), 150)}
			/>
			{#if srcFocused && srcResults.length > 0}
				<div class="results">
					{#each srcResults as r}
						<div class="result" on:click={() => selectResult(r, 'src')}>
							{r.name} ({r.papers} papers)
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<div class="autocomplete">
			<input
				type="text"
				placeholder="Target author"
				bind:value={targetAid}
				on:focus={() => (targetFocused = true)}
				on:input={(e) => fetchResults(e.target.value, 'target')}
				on:blur={() => setTimeout(() => (targetFocused = false), 150)}
			/>
			{#if targetFocused && targetResults.length > 0}
				<div class="results">
					{#each targetResults as r}
						<div class="result" on:click={() => selectResult(r, 'target')}>
							{r.name} ({r.papers} papers)
						</div>
					{/each}
				</div>
			{/if}
		</div>
	</div>

	{#if hits.targetName != '' && hits.srcName != ''}
		<h1>Citation Connections of Hit Papers by {hits.targetName} citing papers by {hits.srcName}</h1>
		<span
			>Papers authored by {hits.srcName} in the citation tree are
			<span class="relevant">highlighted</span>. Hovering a paper, highlights which papers are
			citing it the level above</span
		>
	{/if}

	{#each hits.paths as hit}
		{#if hit.tree != 'Leaf' && Object.keys(hit.tree.Node).length > 0}
			<div class="hit shadowy padded marged">
				<h2><a href="https://doi.org/{hit.doi}" target="_blank">{hit.title}</a> ({hit.year})</h2>
				<RefTreeTable
					tree={hit.tree}
					relWorks={hits.relWorks}
					doiMap={hits.doiMap}
					nameMap={hits.nameMap}
				/>
			</div>
		{/if}
	{/each}
</div>

<style>
	h1 {
		margin-bottom: 18px;
	}

	.container {
		max-width: 1200px;
		padding-top: 80px;
		margin: auto;
	}
	.hit > h2 {
		margin-top: 0px;
	}
	.control {
		display: flex;
		gap: 1rem;
		margin-bottom: 2rem;
	}
	input {
		width: 100%;
		padding: 0.5rem;
		font-size: 1rem;
	}
	.autocomplete {
		position: relative;
		width: 100%;
	}
	.results {
		position: absolute;
		top: 100%;
		left: 0;
		right: 0;
		background: var(--text-bg);
		border: 1px solid #ccc;
		z-index: 10;
		max-height: 200px;
		overflow-y: auto;
		box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
	}
	.result {
		padding: 0.4rem 0.6rem;
		cursor: pointer;
	}
	.result:hover {
		background: var(--text-bg-2);
	}

	.relevant {
		background-color: var(--text-bg-3);
	}
</style>
