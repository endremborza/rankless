<script lang="ts">
	import { BE_REMOTE_URL } from '$lib/constants.js';
	import { formatNumber } from '$lib/text-format-util';
	import { entToLink } from '$lib/tree-functions';
	import { onMount } from 'svelte';

	export let data;

	let papersResp: any = null;
	let selectedStyle = 'APA';
	let sortBy: 'year' | 'citations' = 'year';
	let minCitations = 0;

	onMount(() => {
		if (data.searchResult) {
			fetch(`${BE_REMOTE_URL}/works/authors/${data.searchResult.semanticId}/0`)
				.then((resp) => resp.json())
				.then((obj) => {
					papersResp = obj;
				});
		}
	});

	function formatAuthors(authorIds: string[], authorNames: Record<string, string>, style: string) {
		if (!authorIds || authorIds.length === 0) return '';
		const names = authorIds.map((id) => authorNames[id] || id);

		const formatted = names.map((full) => {
			const parts = full.split(' ');
			const last = parts.pop();
			const initials = parts.map((p) => p[0].toUpperCase() + '.').join(' ');
			return `${last}, ${initials}`;
		});

		if (style === 'MLA') {
			if (formatted.length === 1) return formatted[0];
			if (formatted.length === 2) return `${formatted[0]} and ${formatted[1]}`;
			return `${formatted[0]}, et al.`;
		}

		// APA or Chicago
		if (formatted.length === 1) return formatted[0];
		if (formatted.length === 2) return `${formatted[0]} & ${formatted[1]}`;
		if (formatted.length <= 5) return formatted.slice(0, -1).join(', ') + ', & ' + formatted.at(-1);
		return formatted.slice(0, 5).join(', ') + ', et al.';
	}

	function formatPaper(paper, style) {
		if (!papersResp) return '';
		const authors = formatAuthors(paper.authors, papersResp.author_names || {}, style);
		const title = paper.name;
		const journal = papersResp.labels.sources[paper.source]?.name ?? '';
		const year = paper.year;
		const vol = paper.biblio.volume ? `, ${paper.biblio.volume}` : '';
		const issue = paper.biblio.issue ? `(${paper.biblio.issue})` : '';
		const pages =
			paper.biblio.first_page && paper.biblio.last_page
				? `, pp. ${paper.biblio.first_page}–${paper.biblio.last_page}`
				: '';
		const doi = paper.doi ? `https://doi.org/${paper.doi}` : '';

		switch (style) {
			case 'MLA':
				return `${authors}. “${title}.” *${journal}* ${vol}${issue} (${year})${pages}. ${doi}`;
			case 'Chicago':
				return `${authors}. "${title}." *${journal}* ${vol}${issue} (${year}): ${
					paper.biblio.first_page ?? ''
				}–${paper.biblio.last_page ?? ''}. ${doi}`;
			default: // APA
				return `${authors} (${year}). ${title}. *${journal}*${vol}${issue}${pages}. ${doi}`;
		}
	}

	// Derived list: filtered + sorted
	$: filteredAndSorted =
		papersResp?.papers
			.filter((p) => p.citations >= minCitations)
			.sort((a, b) => {
				if (sortBy === 'year') return b.year - a.year;
				if (sortBy === 'citations') return b.citations - a.citations;
				return 0;
			}) ?? [];
</script>

<div class="container padded">
	{#if data.user}
		<h1>Welcome, {data.user.name}!</h1>
		<p>Your ORCID iD: {data.user.orcid}</p>

		{#if data.searchResult}
			<span>
				Your profile:
				<h3>
					<a href={entToLink(data.searchResult)}>{data.searchResult.name}</a>
				</h3>
				<span>
					{formatNumber(data.searchResult.papers, 0)} papers,
					{formatNumber(data.searchResult.citations, 0)} citations
				</span>
			</span>

			{#if papersResp}
				<hr />
				<h2>Your Publications</h2>

				<div class="controls">
					<div>
						<label for="style">Citation style:</label>
						<select id="style" bind:value={selectedStyle}>
							<option value="APA">APA</option>
							<option value="MLA">MLA</option>
							<option value="Chicago">Chicago</option>
						</select>
					</div>

					<div>
						<label for="sort">Sort by:</label>
						<select id="sort" bind:value={sortBy}>
							<option value="year">Year (newest first)</option>
							<option value="citations">Citations (most cited first)</option>
						</select>
					</div>

					<div>
						<label for="mincit">Min. citations:</label>
						<input
							id="mincit"
							type="number"
							bind:value={minCitations}
							min="0"
							style="width: 5em;"
						/>
					</div>
				</div>

				<ol class="citations">
					{#each filteredAndSorted as paper}
						<li>{formatPaper(paper, selectedStyle)}</li>
					{:else}
						<li><em>No papers match the current filters.</em></li>
					{/each}
				</ol>
			{/if}
		{:else}
			You seem to have no Rankless profile
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
	.controls {
		display: flex;
		flex-wrap: wrap;
		gap: 1rem;
		align-items: center;
		margin-bottom: 1rem;
	}
	select,
	input {
		margin-left: 0.3rem;
	}
	.citations {
		line-height: 1.5;
	}
	.citations li {
		margin-bottom: 0.8rem;
	}
</style>
