<script lang="ts">
	import { goto } from '$app/navigation';
	import { BE_REMOTE_URL } from '$lib/constants';
	import type { SearchResult } from '$lib/tree-types';

	let srcQuery = '';
	let targetQuery = '';
	let srcResults: SearchResult[] = [];
	let targetResults: SearchResult[] = [];
	let srcSelected: SearchResult | null = null;
	let targetSelected: SearchResult | null = null;
	let srcFocused = false;
	let targetFocused = false;

	async function search(q: string): Promise<SearchResult[]> {
		if (q.length < 2) return [];
		const res = await fetch(`${BE_REMOTE_URL}/names/authors?` + new URLSearchParams({ q }));
		const results: SearchResult[] = await res.json();
		return results.map((e) => ({ ...e, rootType: 'authors' as const }));
	}

	async function onSrcInput() {
		srcSelected = null;
		srcResults = await search(srcQuery);
	}

	async function onTargetInput() {
		targetSelected = null;
		targetResults = await search(targetQuery);
	}

	function selectSrc(r: SearchResult) {
		srcSelected = r;
		srcQuery = r.name;
		srcResults = [];
		maybeNavigate();
	}

	function selectTarget(r: SearchResult) {
		targetSelected = r;
		targetQuery = r.name;
		targetResults = [];
		maybeNavigate();
	}

	function maybeNavigate() {
		if (srcSelected && targetSelected) {
			goto(`/path-to-person/${srcSelected.semanticId}/${targetSelected.semanticId}`);
		}
	}
</script>

<div class="container shadowy padded marged">
	<h1>Path to Person</h1>
	<p class="subtitle">Find how an author's papers are cited by another author's work.</p>

	<div class="inputs">
		<div class="search-box">
			<label for="src-input">Source author (whose papers get cited)</label>
			<input
				id="src-input"
				type="text"
				bind:value={srcQuery}
				on:input={onSrcInput}
				on:focus={() => (srcFocused = true)}
				on:blur={() => setTimeout(() => (srcFocused = false), 150)}
				placeholder="Search for an author…"
				autocomplete="off"
			/>
			{#if srcFocused && srcResults.length > 0}
				<ul class="dropdown">
					{#each srcResults as r}
						<!-- svelte-ignore a11y-click-events-have-key-events -->
						<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
						<li on:click={() => selectSrc(r)}>
							<strong>{r.name}</strong>
							<span>{r.papers} papers · {r.citations} citations</span>
						</li>
					{/each}
				</ul>
			{/if}
		</div>

		<div class="search-box">
			<label for="target-input">Target author (whose work cites)</label>
			<input
				id="target-input"
				type="text"
				bind:value={targetQuery}
				on:input={onTargetInput}
				on:focus={() => (targetFocused = true)}
				on:blur={() => setTimeout(() => (targetFocused = false), 150)}
				placeholder="Search for an author…"
				autocomplete="off"
			/>
			{#if targetFocused && targetResults.length > 0}
				<ul class="dropdown">
					{#each targetResults as r}
						<!-- svelte-ignore a11y-click-events-have-key-events -->
						<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
						<li on:click={() => selectTarget(r)}>
							<strong>{r.name}</strong>
							<span>{r.papers} papers · {r.citations} citations</span>
						</li>
					{/each}
				</ul>
			{/if}
		</div>
	</div>
</div>

<style>
	.container {
		max-width: 800px;
		margin: 100px auto 40px;
	}

	.subtitle {
		opacity: 0.7;
		margin-bottom: 40px;
	}

	.inputs {
		display: flex;
		gap: 32px;
		flex-wrap: wrap;
	}

	.search-box {
		flex: 1;
		min-width: 260px;
		position: relative;
	}

	label {
		display: block;
		font-size: 0.8rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		margin-bottom: 6px;
		opacity: 0.7;
	}

	input {
		width: 100%;
		box-sizing: border-box;
		padding: 10px 14px;
		font-size: 1rem;
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
		font-size: 0.75rem;
		opacity: 0.6;
	}
</style>
