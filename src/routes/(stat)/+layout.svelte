<script lang="ts">
	import SearchLogo from '$lib/components/SearchLogo.svelte';
	import SearchResults from '$lib/components/SearchResults.svelte';
	import TextedLogo from '$lib/components/TextedLogo.svelte';
	import PathLogo from '$lib/components/PathLogo.svelte';
	import SurveyPrompt from '$lib/components/SurveyPrompt.svelte';
	import { afterNavigate } from '$app/navigation';
	import { onMount, tick } from 'svelte';
	import { slide } from 'svelte/transition';

	import type { RootType } from '$lib/tree-types';
	import { LATEST_YEAR, ROOT_TYPES } from '$lib/constants';
	import { prettifyRoot } from '$lib/text-format-util';
	import { resultsHidden } from '$lib/stores';

	export let data: { surveyShouldPrompt: boolean };
	let options: RootType[] = ROOT_TYPES.filter((e) => e != 'hit-papers');
	let cat: RootType = options[0];

	let mounted = false;
	let dropdownOpen = false;
	// let innerWidth = 900;
	let innerWidth: number;

	$: visibleCount = innerWidth >= 600 ? options.length : innerWidth >= 500 ? 3 : 0;
	$: visibleOptions = options.slice(0, visibleCount);
	$: overflowOptions = options.slice(visibleCount);

	function init(el: HTMLInputElement) {
		el.focus();
	}

	function focusSelect(e: FocusEvent) {
		resultsHidden.set(false);
		if (e.target != undefined) {
			(e.target as HTMLTextAreaElement).select();
		}
	}

	async function openSearchFor(opt: RootType) {
		cat = opt;
		resultsHidden.set(false);
		dropdownOpen = false;
		await tick();
		document.getElementById('search-input')?.focus();
	}

	function toggleSearch() {
		if ($resultsHidden) {
			resultsHidden.set(false);
		} else {
			resultsHidden.set(true);
		}
	}

	onMount(() => {
		mounted = true;
	});

	afterNavigate(() => {
		dropdownOpen = false;
		resultsHidden.set(true);
	});

	let searchTerm = '';

	function keyBind(key: { key: string }) {
		if (key.key == 'Escape') {
			resultsHidden.set(true);
			dropdownOpen = false;
		}
	}

	function setNoScroll(rHide: boolean) {
		if (mounted) {
			if (rHide) {
				document.body.classList.remove('no-scroll');
			} else {
				document.body.classList.add('no-scroll');
			}
		}
	}

	$: currenHidden = $resultsHidden;
	$: setNoScroll(currenHidden);
</script>

<svelte:window on:keydown={keyBind} bind:innerWidth />
<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div id="main-fix">
	<header id="site-header">
		<a href="/" class="header-logo" aria-label="Home">
			<svg viewBox="0 0 20 20">
				<PathLogo />
			</svg>
		</a>

		<nav class="header-nav">
			{#each visibleOptions as opt}
				<button
					class="nav-link"
					class:active={!$resultsHidden && cat === opt}
					on:click={() => openSearchFor(opt)}
				>
					{prettifyRoot(opt)}
				</button>
			{/each}

			{#if overflowOptions.length > 0}
				<div class="dropdown">
					<button
						class="nav-link dropdown-trigger"
						class:active={!$resultsHidden && overflowOptions.includes(cat)}
						on:click={() => (dropdownOpen = !dropdownOpen)}
					>
						{visibleCount === 0 ? 'Search' : 'More'} &#9662;
					</button>
					{#if dropdownOpen}
						<div class="dropdown-menu" transition:slide={{ duration: 150, axis: 'y' }}>
							{#each overflowOptions as opt}
								<button
									class="dropdown-item"
									class:active={!$resultsHidden && cat === opt}
									on:click={() => openSearchFor(opt)}
								>
									{prettifyRoot(opt)}
								</button>
							{/each}
						</div>
					{/if}
				</div>
			{/if}
		</nav>

		<button class="header-search" on:click={toggleSearch} aria-label="Toggle search">
			{#if $resultsHidden}
				<svg viewBox="-10 -10 60 50" fill="none" xmlns="http://www.w3.org/2000/svg">
					<SearchLogo />
				</svg>
			{:else}
				<span class="close-icon">&#10006;</span>
			{/if}
		</button>
	</header>

	{#if !$resultsHidden}
		<div id="search-bar" transition:slide={{ duration: 200, axis: 'y' }}>
			<input
				bind:value={searchTerm}
				on:focus={focusSelect}
				use:init
				type="text"
				id="search-input"
			/>
		</div>
	{/if}

	<SearchResults {searchTerm} {cat} />
	<div id="main-content" on:click={() => (dropdownOpen = false)}>
		<slot />
	</div>
	<div id="main-foot">
		<TextedLogo pad={0} size={30} />
		<span>{LATEST_YEAR}</span>
		<div id="foot-r"><a href="/#contact">Contact</a></div>
	</div>
</div>

{#if data.surveyShouldPrompt}
	<SurveyPrompt />
{/if}

<style>
	#site-header {
		position: sticky;
		top: 0;
		z-index: 25;
		display: flex;
		align-items: center;
		gap: 4px;
		padding: 8px 3vw;
		background-color: var(--color-theme-white);
		border-bottom: solid var(--color-theme-darkblue) 3px;
	}

	.header-logo {
		display: flex;
		align-items: center;
		flex-shrink: 0;
		margin-right: 12px;
	}

	.header-logo svg {
		width: 28px;
		height: 28px;
	}

	.header-nav {
		display: flex;
		align-items: center;
		gap: 2px;
		flex: 1;
	}

	.nav-link {
		background: none;
		border: none;
		font-family: inherit;
		font-size: 0.9rem;
		padding: 6px 10px;
		cursor: pointer;
		color: var(--color-theme-darkgrey);
		border-radius: var(--borad);
		transition: background-color 0.15s, color 0.15s;
		white-space: nowrap;
	}

	.nav-link:hover {
		background-color: var(--color-theme-lightblue);
		color: var(--color-theme-darkblue);
	}

	.nav-link.active {
		color: var(--color-theme-darkblue);
		font-weight: bold;
	}

	.dropdown {
		position: relative;
	}

	.dropdown-menu {
		position: absolute;
		top: 100%;
		left: 0;
		background-color: var(--color-theme-white);
		border: solid var(--color-theme-darkblue) 2px;
		border-radius: var(--borad);
		box-shadow: 2px 4px 12px var(--color-theme-shadow);
		z-index: 20;
		display: flex;
		flex-direction: column;
		min-width: 140px;
		overflow: hidden;
	}

	.dropdown-item {
		background: none;
		border: none;
		font-family: inherit;
		font-size: 0.9rem;
		padding: 8px 14px;
		cursor: pointer;
		color: var(--color-theme-darkgrey);
		text-align: left;
		white-space: nowrap;
		transition: background-color 0.15s, color 0.15s;
	}

	.dropdown-item:hover {
		background-color: var(--color-theme-lightblue);
		color: var(--color-theme-darkblue);
	}

	.dropdown-item.active {
		color: var(--color-theme-darkblue);
		font-weight: bold;
	}

	.header-search {
		background: none;
		border: none;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		padding: 4px;
		margin-left: auto;
	}

	.header-search svg {
		width: 24px;
		height: 24px;
	}

	.close-icon {
		font-size: 22px;
		line-height: 1;
		color: var(--color-theme-darkgrey);
		transition: color 0.15s;
	}

	.close-icon:hover {
		color: var(--color-theme-darkblue);
	}

	#search-bar {
		position: sticky;
		top: 48px;
		z-index: 24;
		background-color: var(--color-theme-white);
		padding: 8px 3vw;
		border-bottom: solid var(--color-theme-darkblue) 1px;
	}

	#search-input {
		width: 100%;
		height: 35px;
		border: none;
		font-size: 22px;
		font-style: italic;
		font-family: inherit;
		background: none;
		text-indent: 8px;
		box-sizing: border-box;
	}

	#search-input:hover {
		background-color: rgba(171, 171, 171, 0.15);
	}

	#search-input:focus {
		outline: none;
	}

	#main-fix {
		display: flex;
		flex-flow: column;
		min-height: 100dvh;
	}

	#main-content {
		flex: 1 1 auto;
	}

	#main-foot {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding-left: 3vw;
		padding-right: 3vw;
		padding-top: 3px;
		padding-bottom: 3px;
		background-color: var(--color-theme-yellow);
		color: var(--color-theme-darkgrey);
		flex: 0 0 50px;
		z-index: 1;
		height: min(50px, 3svh);
	}

	#foot-r > a {
		color: var(--color-theme-darkgrey);
	}
</style>
