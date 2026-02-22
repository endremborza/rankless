<script lang="ts">
	import { APP_NAME, BE_REMOTE_URL } from '$lib/constants';
	import type { View, SearchResult, PathResp } from '$lib/tree-types';
	import PaperRainbow from '$lib/components/PaperRainbow.svelte';
	import RefTreeTable from '$lib/components/RefTreeTable.svelte';

	export let data: {
		view: View;
		semanticId: string;
		paperText: string;
		citeText: string;
	};

	let targetQuery = '';
	let targetResults: SearchResult[] = [];
	let targetFocused = false;
	let pathResp: PathResp | null = null;
	let pathLoading = false;
	let pathError = '';

	async function searchAuthors(q: string): Promise<SearchResult[]> {
		if (q.length < 2) return [];
		const res = await fetch(`${BE_REMOTE_URL}/names/authors?` + new URLSearchParams({ q }));
		const results: SearchResult[] = await res.json();
		return results.map((e) => ({ ...e, rootType: 'authors' as const }));
	}

	async function onTargetInput() {
		pathResp = null;
		pathError = '';
		targetResults = await searchAuthors(targetQuery);
	}

	async function selectTarget(r: SearchResult) {
		targetQuery = r.name;
		targetResults = [];
		pathLoading = true;
		pathError = '';
		pathResp = null;
		try {
			const res = await fetch(
				`${BE_REMOTE_URL}/path-to-paper/${data.semanticId}/${r.semanticId}/true`
			);
			if (!res.ok) throw new Error('Not found');
			pathResp = await res.json();
		} catch {
			pathError = 'Could not find citation paths between these authors.';
		} finally {
			pathLoading = false;
		}
	}
</script>

<svelte:head>
	<title>{APP_NAME} | {data.view.name} – Papers & Paths</title>
	<meta
		name="description"
		content="Top papers and citation paths for {data.view.name} – {data.paperText}, {data.citeText}"
	/>
</svelte:head>

<div id="head" class="shadowy padded marged">
	<a href="/authors/{data.semanticId}" class="back-link">← Back to full profile</a>
	<h1>{data.view.name}</h1>
	<p class="stats">{data.paperText} · {data.citeText}</p>
</div>

{#if data.view.hitPapers.length > 0}
	<div class="shadowy padded marged">
		<h2>Top Papers</h2>
		<PaperRainbow papers={data.view.hitPapers} />
	</div>
{/if}

<div class="shadowy padded marged" id="path-finder">
	<h2>Citation Paths</h2>
	<p class="section-desc">
		Find how <strong>{data.view.name}</strong>'s papers are connected to another author through
		citations.
	</p>

	<div class="search-box">
		<label for="target-input">Search for an author</label>
		<input
			id="target-input"
			type="text"
			bind:value={targetQuery}
			on:input={onTargetInput}
			on:focus={() => (targetFocused = true)}
			on:blur={() => setTimeout(() => (targetFocused = false), 150)}
			placeholder="Type a name…"
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

	{#if pathLoading}
		<p class="status">Loading citation paths…</p>
	{:else if pathError}
		<p class="status error">{pathError}</p>
	{:else if pathResp}
		{#if pathResp.paths.length === 0}
			<p class="status">No citation paths found between these authors.</p>
		{:else}
			<div class="path-results">
				{#each pathResp.paths as pathEntry}
					<div class="path-block">
						<h3>
							{#if pathEntry.doi}
								<a href="https://doi.org/{pathEntry.doi}" target="_blank"
									>{pathEntry.title}</a
								>
							{:else}
								{pathEntry.title}
							{/if}
							{#if pathEntry.year}
								<span class="year">({pathEntry.year})</span>
							{/if}
						</h3>
						<RefTreeTable
							tree={pathEntry.tree}
							nameMap={pathResp.nameMap}
							doiMap={pathResp.doiMap}
							relWorks={pathResp.relWorks}
						/>
					</div>
				{/each}
			</div>
		{/if}
	{/if}
</div>

<style>
	#head {
		margin-top: var(--unified-margin);
	}

	.back-link {
		font-size: 0.8rem;
		opacity: 0.6;
		text-decoration: none;
		color: var(--color-text);
		transition: opacity 0.15s;
	}

	.back-link:hover {
		opacity: 1;
	}

	h1 {
		margin-top: 4px;
	}

	.stats {
		opacity: 0.6;
		margin-top: 4px;
	}

	h2 {
		margin-bottom: 8px;
	}

	.section-desc {
		opacity: 0.7;
		margin-bottom: 24px;
	}

	.search-box {
		position: relative;
		max-width: 480px;
		margin-bottom: 24px;
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

	.status {
		opacity: 0.6;
		font-style: italic;
	}

	.error {
		color: salmon;
	}

	.path-results {
		margin-top: 16px;
	}

	.path-block {
		margin-bottom: 40px;
	}

	h3 {
		margin-bottom: 8px;
	}

	.year {
		font-weight: normal;
		opacity: 0.6;
		font-size: 0.85em;
	}
</style>
