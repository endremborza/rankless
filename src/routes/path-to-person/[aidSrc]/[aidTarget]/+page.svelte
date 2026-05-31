<script lang="ts">
	import { goto } from '$app/navigation';
	import { BE_REMOTE_URL } from '$lib/constants';
	import type { PathResp, SearchResult } from '$lib/tree-types';
	import RefTreeTable from '$lib/components/RefTreeTable.svelte';

	export let data: { srcAid: string; targetAid: string };

	let srcQuery = '';
	let targetQuery = '';
	let srcResults: SearchResult[] = [];
	let targetResults: SearchResult[] = [];
	let srcFocused = false;
	let targetFocused = false;
	let pathResp: PathResp | null = null;
	let loading = false;
	let errorMsg = '';

	async function search(q: string): Promise<SearchResult[]> {
		if (q.length < 2) return [];
		const res = await fetch(`${BE_REMOTE_URL}/names/authors?` + new URLSearchParams({ q }));
		const results: SearchResult[] = await res.json();
		return results.map((e) => ({ ...e, rootType: 'authors' as const }));
	}

	async function onSrcInput() {
		srcResults = await search(srcQuery);
	}

	async function onTargetInput() {
		targetResults = await search(targetQuery);
	}

	function selectSrc(r: SearchResult) {
		srcQuery = r.name;
		srcResults = [];
		goto(`/path-to-person/${r.semanticId}/${data.targetAid}`);
	}

	function selectTarget(r: SearchResult) {
		targetQuery = r.name;
		targetResults = [];
		goto(`/path-to-person/${data.srcAid}/${r.semanticId}`);
	}

	async function fetchPaths(srcAid: string, targetAid: string) {
		if (!srcAid || !targetAid) return;
		loading = true;
		errorMsg = '';
		pathResp = null;
		try {
			const res = await fetch(`${BE_REMOTE_URL}/path-to-paper/${srcAid}/${targetAid}/true`);
			if (!res.ok) throw new Error('Not found');
			pathResp = await res.json();
			if (pathResp) {
				srcQuery = pathResp.srcName;
				targetQuery = pathResp.targetName;
			}
		} catch {
			errorMsg = 'No paths found or an error occurred.';
		} finally {
			loading = false;
		}
	}

	$: fetchPaths(data.srcAid, data.targetAid);
</script>

<div class="container marged">
	<div class="inputs shadowy padded">
		<div class="search-box">
			<label for="src-input">Source author (cited)</label>
			<input
				id="src-input"
				type="text"
				bind:value={srcQuery}
				on:input={onSrcInput}
				on:focus={() => (srcFocused = true)}
				on:blur={() => setTimeout(() => (srcFocused = false), 150)}
				autocomplete="off"
			/>
			{#if srcFocused && srcResults.length > 0}
				<ul class="dropdown">
					{#each srcResults as r}
						<!-- svelte-ignore a11y_click_events_have_key_events -->
						<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
						<li on:click={() => selectSrc(r)}>
							<strong>{r.name}</strong>
							<span>{r.papers} papers · {r.citations} citations</span>
						</li>
					{/each}
				</ul>
			{/if}
		</div>

		<div class="search-box">
			<label for="target-input">Target author (citing)</label>
			<input
				id="target-input"
				type="text"
				bind:value={targetQuery}
				on:input={onTargetInput}
				on:focus={() => (targetFocused = true)}
				on:blur={() => setTimeout(() => (targetFocused = false), 150)}
				autocomplete="off"
			/>
			{#if targetFocused && targetResults.length > 0}
				<ul class="dropdown">
					{#each targetResults as r}
						<!-- svelte-ignore a11y_click_events_have_key_events -->
						<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
						<li on:click={() => selectTarget(r)}>
							<strong>{r.name}</strong>
							<span>{r.papers} papers · {r.citations} citations</span>
						</li>
					{/each}
				</ul>
			{/if}
		</div>
	</div>

	{#if loading}
		<p class="status">Loading paths…</p>
	{:else if errorMsg}
		<p class="status error">{errorMsg}</p>
	{:else if pathResp}
		<div class="results shadowy padded">
			<h1>
				Citation paths from <em>{pathResp.srcName}</em> to <em>{pathResp.targetName}</em>
			</h1>
			{#if pathResp.paths.length === 0}
				<p class="status">No citation paths found between these authors.</p>
			{:else}
				{#each pathResp.paths as pathEntry}
					<div class="path-block">
						<h2>
							{#if pathEntry.doi}
								<a href="https://doi.org/{pathEntry.doi}" target="_blank">{pathEntry.title}</a>
							{:else}
								{pathEntry.title}
							{/if}
							{#if pathEntry.year}
								<span class="year">({pathEntry.year})</span>
							{/if}
						</h2>
						<RefTreeTable
							tree={pathEntry.tree}
							nameMap={pathResp.nameMap}
							doiMap={pathResp.doiMap}
							relWorks={pathResp.relWorks}
						/>
					</div>
				{/each}
			{/if}
		</div>
	{/if}
</div>

<style>
	.container {
		max-width: 1100px;
		margin-top: 80px;
	}

	.inputs {
		display: flex;
		gap: 32px;
		flex-wrap: wrap;
		margin-bottom: 24px;
	}

	.search-box {
		flex: 1;
		min-width: 260px;
		position: relative;
	}

	label {
		display: block;
		font-size: var(--text-sm);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		margin-bottom: 6px;
		opacity: 0.7;
	}

	input {
		width: 100%;
		box-sizing: border-box;
		padding: 10px 14px;
		font-size: var(--text-md);
		border: solid 1px var(--color-theme-blue);
		background: var(--text-bg-2);
		color: var(--color-text);
	}

	.dropdown {
		position: absolute;
		left: 0;
		right: 0;
		background: var(--text-bg-2);
		border: solid 1px var(--color-theme-blue);
		border-top: none;
		list-style: none;
		margin: 0;
		padding: 0;
		z-index: 10;
		max-height: 300px;
		overflow-y: auto;
	}

	.dropdown li {
		padding: 10px 14px;
		cursor: pointer;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.dropdown li:hover {
		background: rgba(var(--color-range-15), 0.15);
	}

	.dropdown li span {
		font-size: var(--text-sm);
		opacity: 0.6;
	}

	.error {
		color: salmon;
	}

	.path-block {
		margin-bottom: 40px;
	}

	.year {
		font-weight: normal;
		opacity: 0.6;
		font-size: 0.85em;
	}

	h2 {
		margin-bottom: 8px;
	}
</style>
