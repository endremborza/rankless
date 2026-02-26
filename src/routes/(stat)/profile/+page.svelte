<script lang="ts">
	import { BE_REMOTE_URL } from '$lib/constants.js';
	import { onMount } from 'svelte';
	import type { Paper, EntityAttsForLinks } from '$lib/tree-types';
	import {
		formatReference,
		toBibtexFile,
		type CitationStyle
	} from '$lib/utils/reference-format';
	import { copyToClipboard, downloadTextFile } from '$lib/utils/clipboard-download';

	export let data: { user?: any; searchResult?: any };

	let papers: Paper[] = [];
	let entityAtts: EntityAttsForLinks = {};
	let discAuthorNames: Record<string, string> = {};
	let sortBy: 'year' | 'citations' = 'year';
	let minCitations = 0;
	let includeDoi = true;
	let citationStyle: CitationStyle = 'chicago';

	onMount(async () => {
		if (data.searchResult) {
			const resp = await fetch(`${BE_REMOTE_URL}/works/authors/${data.searchResult.semanticId}/0`);
			const obj = await resp.json();
			papers = obj.resp?.papers || [];
			entityAtts = obj.resp?.entityAtts || {};
			discAuthorNames = obj.resp?.discAuthorNames || {};
		}
	});

	$: filteredPapers = papers
		.filter((p) => p.citations >= minCitations)
		.sort((a, b) => (sortBy === 'citations' ? b.citations - a.citations : b.year - a.year));

	function handleCopyBibtex() {
		const bib = toBibtexFile(filteredPapers, entityAtts, discAuthorNames);
		copyToClipboard(bib);
	}

	function handleDownloadBibtex() {
		const bib = toBibtexFile(filteredPapers, entityAtts, discAuthorNames);
		downloadTextFile('papers.bib', bib);
	}
</script>

<div class="container padded">
	{#if data.user}
		<h1>Welcome, {data.user.name}!</h1>
		<p>Your ORCID iD: {data.user.orcid}</p>

		{#if data.searchResult}
			<section>
				<h3>
					<a href={data.searchResult.url}>{data.searchResult.name}</a>
				</h3>
				<p>
					{data.searchResult.papers} papers, {data.searchResult.citations} citations
				</p>
			</section>

			<hr />

			{#if papers.length > 0}
				<div class="controls">
					<label>
						Sort by:
						<select bind:value={sortBy}>
							<option value="year">Year (desc)</option>
							<option value="citations">Citations (desc)</option>
						</select>
					</label>

					<label>
						Min citations:
						<input type="number" min="0" bind:value={minCitations} />
					</label>

					<label>
						Style:
						<select bind:value={citationStyle}>
							<option value="chicago">Chicago</option>
							<option value="apa">APA</option>
							<option value="mla">MLA</option>
						</select>
					</label>

					<label>
						<input type="checkbox" bind:checked={includeDoi} />
						Include DOI
					</label>

					<button on:click={handleCopyBibtex}>Copy BibTeX</button>
					<button on:click={handleDownloadBibtex}>Download .bib</button>
				</div>

				<ul class="references">
					{#each filteredPapers as paper}
						<li>{formatReference(paper, entityAtts, discAuthorNames, citationStyle, includeDoi)}</li>
					{/each}
				</ul>
			{:else}
				<p>Loading papers...</p>
			{/if}
		{/if}

		<hr />
		<a href="/logout">Logout</a>
	{:else}
		<h1>Not logged in</h1>
		<a href="/login">Login with ORCID</a>
	{/if}
</div>

<style>
	.container {
		max-width: 800px;
		margin: auto;
		padding-top: 110px;
	}
	select,
	input {
		margin-left: 0.3rem;
	}
	.controls {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
		align-items: center;
		margin-bottom: 1rem;
	}
	.references {
		list-style: none;
		padding: 0;
	}
	.references li {
		margin-bottom: 0.75rem;
	}
</style>
