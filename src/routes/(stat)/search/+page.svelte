<script lang="ts">
	import SearchResults from '$lib/components/SearchResults.svelte';
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
		<SearchResults searchTerm={q} cat="all" overlay={false} />
	{:else}
		<p class="search-hint">
			Type a query above to search across authors, institutions, journals, countries and research
			fields.
		</p>
	{/if}
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

	.search-hint {
		opacity: 0.6;
	}
</style>
