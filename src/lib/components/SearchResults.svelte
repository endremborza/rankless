<script lang="ts">
	import { formatNumber } from '$lib/text-format-util';
	import { BE_REMOTE_URL } from '$lib/constants';
	import type { RootType, SearchResult } from '$lib/tree-types';
	import { entToLink } from '$lib/tree-functions';
	import { onMount } from 'svelte';

	export let searchTerm: string;
	export let cat: RootType;
	export let resultsHidden: boolean;

	let mounted = false;
	let delayedTerm = '';
	let searchResults: SearchResult[] = [];

	function getSearchResults(searchTerm: string, cat: RootType, mounted: boolean) {
		if (!mounted || cat == undefined) {
			return;
		}
		delayedTerm = searchTerm;
		fetch(
			`${BE_REMOTE_URL}/names/${cat}?` +
				new URLSearchParams({
					q: searchTerm
				}).toString()
		)
			.then((res) => res.json())
			.then((l: SearchResult[]) => {
				if (delayedTerm == searchTerm) {
					searchResults = l.map((e) => {
						return { ...e, rootType: cat };
					});
				}
			});
	}

	onMount(() => {
		mounted = true;
	});

	$: getSearchResults(searchTerm, cat, mounted);
</script>

<div class="search-results" style="display: {resultsHidden ? 'none' : 'flex'};">
	{#each searchResults as searchResult}
		<a class="result-card shadowy padded" href={entToLink(searchResult)}>
			<h3 style="font-size: {searchResult.name.length > 50 ? 1.2 : 1.45}em;">
				{searchResult.name}
			</h3>
			<span class="subtitle"
				>{formatNumber(searchResult.papers, 0)} papers,
				{formatNumber(searchResult.citations, 0)} citations</span
			>
		</a>
	{/each}
</div>

<style>
	h3 {
		margin: 0px;
		margin-bottom: 12px;
	}

	.search-results {
		width: 100%;
		height: 100dvh;
		overflow: scroll;
		box-sizing: border-box;
		backdrop-filter: blur(6px);
		-webkit-backdrop-filter: blur(6px);
		position: fixed;
		top: 0px;
		left: 0px;
		z-index: 20;
		flex-direction: rows;
		flex-wrap: wrap;
		justify-content: space-around;
		align-items: start;
		padding-top: 180px;
	}

	.result-card {
		cursor: pointer;
		height: 210px;
		min-width: 240px;
		background-color: var(--text-bg-2);
		border: solid var(--color-theme-darkblue) 1px;
		margin: 40px;
		margin-bottom: var(--unified-margin);
		margin-top: 0px;
		flex: 0 0 18%;
		display: flex;
		flex-direction: column;
		justify-content: space-around;
		transition: transform 0.2s ease;
		z-index: 20;
	}

	.result-card:hover {
		transform: translateY(-10px);
		background-color: var(--color-theme-lightgrey);
		color: var(--color-theme-darkblue);
		box-shadow: 3px 3px 13px var(--color-theme-shadow);
	}
</style>
