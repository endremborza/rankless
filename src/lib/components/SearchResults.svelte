<script lang="ts">
	import { pluralize, rootEmoji, formatNumber } from '$lib/text-format-util';
	import { BE_REMOTE_URL } from '$lib/constants';
	import type { RootType, SearchResult } from '$lib/tree-types';
	import { entToLink } from '$lib/tree-functions';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { resultsHidden } from '$lib/stores';
	import HitPaperExplainer from './HitPaperExplainer.svelte';

	export let searchTerm: string;
	export let cat: RootType | 'all';
	export let disclaimerPosition: 'top' | 'bottom' = 'bottom';
	// Overlay (default) floats over the page as a slightly-opaque panel toggled by `resultsHidden`;
	// inline mode (e.g. the /search page) renders the same list in normal document flow.
	export let overlay = true;
	// Keyboard-highlighted option index, driven by the parent's combobox key handling. Bound out so
	// the parent input can mirror it in `aria-activedescendant`.
	export let activeIndex = -1;
	// Distinct id per instance so the overlay and the inline /search list never collide in the DOM.
	export let listboxId = 'search-listbox';

	let mounted = false;
	let loading = false;
	let delayedTerm = '';
	let debounceTimer: ReturnType<typeof setTimeout> | undefined;
	let results: SearchResult[] = [];

	export function move(delta: number) {
		if (results.length === 0) return;
		let next = activeIndex + delta;
		if (next < 0) next = results.length - 1;
		else if (next >= results.length) next = 0;
		activeIndex = next;
		document
			.getElementById(`${listboxId}-opt-${activeIndex}`)
			?.scrollIntoView({ block: 'nearest' });
	}

	export function openActive(): boolean {
		if (activeIndex < 0 || activeIndex >= results.length) return false;
		goto(entToLink(results[activeIndex]));
		return true;
	}

	async function getSearchResults(searchTerm: string, cat: RootType | 'all') {
		delayedTerm = searchTerm;
		loading = true;
		try {
			const res = await fetch(
				`${BE_REMOTE_URL}/names/${cat}?` + new URLSearchParams({ q: searchTerm }).toString()
			);
			const l: SearchResult[] = await res.json();
			if (delayedTerm == searchTerm) {
				results = l.map((e) => {
					return { ...e, rootType: e.rootType ?? (cat as RootType) };
				});
				activeIndex = -1;
			}
		} catch (e) {
			console.error('search failed', e);
		} finally {
			if (delayedTerm == searchTerm) loading = false;
		}
	}

	function scheduleSearch(searchTerm: string, cat: RootType | 'all', mounted: boolean) {
		if (!mounted || cat == undefined) return;
		clearTimeout(debounceTimer);
		debounceTimer = setTimeout(() => getSearchResults(searchTerm, cat), 180);
	}

	onMount(() => {
		mounted = true;
	});

	$: hidden = overlay && $resultsHidden;
	$: scheduleSearch(searchTerm, cat, mounted);
</script>

<div class="search-results" class:overlay class:hidden>
	{#if cat === 'hit-papers' && disclaimerPosition === 'top'}
		<div class="disclaimer-wrap">
			<HitPaperExplainer />
		</div>
	{/if}
	{#if results.length > 0}
		<ul class="result-list" role="listbox" id={listboxId}>
			{#each results as r, i (i)}
				<li
					class="result-item"
					class:active={i === activeIndex}
					role="option"
					id={`${listboxId}-opt-${i}`}
					aria-selected={i === activeIndex}
				>
					<a class="result-link" href={entToLink(r)} on:mouseenter={() => (activeIndex = i)}>
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
	{:else if loading}
		<p class="search-status">Searching…</p>
	{:else if delayedTerm.trim() !== ''}
		<p class="search-status">No matches for “{delayedTerm}”.</p>
	{/if}
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
		align-items: flex-start;
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
		/* Left padding matches the search bar's 3vw so the list lines up under where you type. */
		padding: 120px 3vw 40px;
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

	.result-link:hover,
	.result-item.active > .result-link {
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

	.search-status {
		margin: 0;
		padding: 11px 16px;
		font-size: var(--text-sm);
		opacity: 0.6;
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
