<script lang="ts">
	import SearchResults from '$lib/components/SearchResults.svelte';
	import { COHORT_ROOT_TYPES } from '$lib/constants';
	import { prettifyRoot } from '$lib/text-format-util';
	import type { PageData } from './$types';

	export let data: PageData;
	$: q = data.q;
</script>

<svelte:head>
	<title>{q ? `Search: ${q}` : 'Search'} · Rankless</title>
</svelte:head>

<section class="shadowy padded marged main-block search-page">
	<h1>Search</h1>
	<form method="get" action="/search" class="search-form">
		<input
			type="search"
			name="q"
			value={q}
			placeholder="Search authors, institutions, journals, countries, fields…"
			aria-label="Search query"
		/>
		<button type="submit">Search</button>
	</form>
	{#if q}
		<SearchResults searchTerm={q} cat="all" overlay={false} listboxId="search-page-list" />
	{:else}
		<p class="search-hint">
			Type a query above to search across authors, institutions, journals, countries and research
			fields.
		</p>
	{/if}
	<p class="browse">
		Or browse every
		{#each COHORT_ROOT_TYPES as rt, i (i)}<a href="/{rt}/table">{prettifyRoot(rt)}</a>{i <
			COHORT_ROOT_TYPES.length - 1
				? ', '
				: ''}{/each} ranked by citations, papers or impact.
	</p>
</section>

<style>
	.search-page {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.search-form {
		display: flex;
		gap: 8px;
	}

	.search-form input {
		flex: 1;
		min-width: 0;
		padding: 8px 12px;
		font-size: var(--text-base);
	}

	.search-form button {
		padding: 8px 16px;
		cursor: pointer;
	}

	.search-hint,
	.browse {
		opacity: 0.6;
	}

	.browse a {
		text-transform: capitalize;
	}
</style>
