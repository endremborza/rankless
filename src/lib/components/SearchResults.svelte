<script lang="ts">
	import { pluralize } from '$lib/text-format-util';
	import { BE_REMOTE_URL } from '$lib/constants';
	import type { RootType, SearchResult } from '$lib/tree-types';
	import { entToLink } from '$lib/tree-functions';
	import { onMount } from 'svelte';
	import { resultsHidden } from '$lib/stores';
	import HitPaperExplainer from './HitPaperExplainer.svelte';

	export let searchTerm: string;
	export let cat: RootType;
	export let disclaimerPosition: 'top' | 'bottom' = 'bottom';

	let mounted = false;
	let delayedTerm = '';
	let searchResults: SearchResult[] = [];

	async function getSearchResults(searchTerm: string, cat: RootType, mounted: boolean) {
		if (!mounted || cat == undefined) {
			return;
		}
		delayedTerm = searchTerm;
		try {
			const res = await fetch(
				`${BE_REMOTE_URL}/names/${cat}?` + new URLSearchParams({ q: searchTerm }).toString()
			);
			const l: SearchResult[] = await res.json();
			if (delayedTerm == searchTerm) {
				searchResults = l.map((e) => {
					return { ...e, rootType: cat };
				});
			}
		} catch (e) {
			console.error('search failed', e);
		}
	}

	function getHeaderFontSize(textLen: number) {
		let n = textLen > 50 ? 1 : 1.1;
		if (textLen > 120) {
			n = 0.8;
		}
		return `${n}rem`;
	}

	onMount(() => {
		mounted = true;
	});

	$: currentHidden = $resultsHidden;
	$: getSearchResults(searchTerm, cat, mounted);
</script>

<div class="search-results" style="display: {currentHidden ? 'none' : 'flex'};">
	{#if cat === 'hit-papers' && disclaimerPosition === 'top'}
		<div class="disclaimer-wrap">
			<HitPaperExplainer />
		</div>
	{/if}
	{#each searchResults as searchResult}
		<a class="result-card shadowy padded" href={entToLink(searchResult)}>
			<h3 style="font-size: {getHeaderFontSize(searchResult.name.length)};">
				{@html searchResult.name}
			</h3>
			<span
				>{#if cat !== 'hit-papers'}{pluralize('paper', searchResult.papers)},
				{/if}{pluralize(
					'citation',
					searchResult.citations
				)}{#if searchResult.distinctText != undefined}<br />{searchResult.distinctText}{/if}</span
			>
		</a>
	{/each}
	{#if cat === 'hit-papers' && disclaimerPosition === 'bottom'}
		<div class="disclaimer-wrap">
			<HitPaperExplainer />
		</div>
	{/if}
</div>

<style>
	h3 {
		margin: 0px;
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
		justify-content: center;
		align-items: start;
		padding-top: 120px;
		gap: var(--unified-margin);
	}

	.result-card {
		cursor: pointer;
		height: 160px;
		min-width: 200px;
		background-color: var(--text-bg-2);
		border: solid var(--color-theme-darkblue) 1px;
		margin-bottom: var(--unified-margin);
		margin-top: 0px;
		flex: 0 0 15%;
		display: flex;
		flex-direction: column;
		justify-content: space-between;
		transition: transform 0.2s ease;
		z-index: 20;
	}

	.result-card:hover {
		transform: scale(1.03);
		background-color: var(--color-theme-lightgrey);
		color: var(--color-theme-darkblue);
		box-shadow: 3px 3px 13px var(--color-theme-shadow);
	}

	.result-card > span {
		font-size: 0.9rem;
	}

	.disclaimer-wrap {
		width: 100%;
		padding: 12px 20px;
		box-sizing: border-box;
		background: var(--text-bg-2);
		border: solid var(--color-theme-darkblue) 1px;
	}
</style>
