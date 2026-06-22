<script lang="ts">
	import { pluralize, rootEmoji, formatNumber } from '$lib/text-format-util';
	import { BE_REMOTE_URL } from '$lib/constants';
	import type { RootType, SearchResult } from '$lib/tree-types';
	import { entToLink } from '$lib/tree-functions';
	import { onMount } from 'svelte';
	import { resultsHidden } from '$lib/stores';
	import HitPaperExplainer from './HitPaperExplainer.svelte';

	export let searchTerm: string;
	export let cat: RootType | 'all';
	export let disclaimerPosition: 'top' | 'bottom' = 'bottom';
	// Overlay (default) floats over the page as a slightly-opaque panel toggled by `resultsHidden`;
	// inline mode (e.g. the /search page) renders the same list in normal document flow.
	export let overlay = true;

	let mounted = false;
	let delayedTerm = '';
	let searchResults: SearchResult[] = [];

	async function getSearchResults(searchTerm: string, cat: RootType | 'all', mounted: boolean) {
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
					return { ...e, rootType: e.rootType ?? (cat as RootType) };
				});
			}
		} catch (e) {
			console.error('search failed', e);
		}
	}

	onMount(() => {
		mounted = true;
	});

	$: hidden = overlay && $resultsHidden;
	$: getSearchResults(searchTerm, cat, mounted);
</script>

<div class="search-results" class:overlay class:hidden>
	{#if cat === 'hit-papers' && disclaimerPosition === 'top'}
		<div class="disclaimer-wrap">
			<HitPaperExplainer />
		</div>
	{/if}
	<ul class="result-list">
		{#each searchResults as r, __i (__i)}
			<li class="result-item">
				<a class="result-link" href={entToLink(r)}>
					<span class="result-name">
						{#if cat === 'all'}<span class="type-emoji">{rootEmoji(r.rootType)}</span>
						{/if}{@html r.name}
					</span>
					<span class="result-meta">
						{#if r.rootType !== 'hit-papers'}{pluralize('paper', r.papers)} ·
						{/if}{#if r.rootType === 'authors' && r.rawCites}{formatNumber(r.rawCites)} citations{:else}{pluralize(
								'citation',
								r.citations
							)}{/if}{#if r.distinctText}
							· {r.distinctText}{/if}
					</span>
				</a>
			</li>
		{/each}
	</ul>
	{#if cat === 'hit-papers' && disclaimerPosition === 'bottom'}
		<div class="disclaimer-wrap">
			<HitPaperExplainer />
		</div>
	{/if}
</div>

<style>
	.search-results {
		width: 100%;
		box-sizing: border-box;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--unified-margin);
	}

	.search-results.overlay {
		height: 100dvh;
		overflow: auto;
		backdrop-filter: blur(6px);
		-webkit-backdrop-filter: blur(6px);
		position: fixed;
		top: 0;
		left: 0;
		z-index: 20;
		padding-top: 120px;
	}

	.hidden {
		display: none;
	}

	/* Left-aligned, idiomatic <li> list: name as the primary line, supporting figures below it. Wraps
	   naturally on long names — no per-result font-size juggling, no fixed-height cards. */
	.result-list {
		list-style: none;
		margin: 0;
		padding: 0;
		width: 100%;
		max-width: 760px;
	}

	.search-results.overlay .result-list {
		background: var(--text-bg-2);
		border: 1px solid var(--color-theme-darkblue);
	}

	.result-item + .result-item {
		border-top: 1px solid var(--color-theme-lightgrey);
	}

	.result-link {
		display: block;
		padding: 11px 16px;
		color: var(--color-text);
		text-decoration: none;
	}

	.result-link:hover {
		background-color: var(--color-theme-lightgrey);
		color: var(--color-theme-darkblue);
	}

	.result-name {
		display: block;
		font-size: var(--text-base);
		font-weight: 600;
		line-height: 1.25;
	}

	.result-meta {
		display: block;
		margin-top: 3px;
		font-size: var(--text-sm);
		opacity: 0.75;
	}

	.type-emoji {
		margin-right: 2px;
	}

	.disclaimer-wrap {
		width: 100%;
		max-width: 760px;
		box-sizing: border-box;
		padding: 12px 20px;
		background: var(--text-bg-2);
		border: solid var(--color-theme-darkblue) 1px;
	}
</style>
