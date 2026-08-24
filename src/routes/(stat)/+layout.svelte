<script lang="ts">
	import SearchLogo from '$lib/components/SearchLogo.svelte';
	import SearchResults from '$lib/components/SearchResults.svelte';
	import TextedLogo from '$lib/components/TextedLogo.svelte';
	import PathLogo from '$lib/components/PathLogo.svelte';
	import SurveyPrompt from '$lib/components/SurveyPrompt.svelte';
	import { afterNavigate, goto } from '$app/navigation';
	import { onMount, tick } from 'svelte';
	import { slide } from 'svelte/transition';

	import { page } from '$app/state';
	import type { RootType } from '$lib/tree-types';
	import { EMAIL_FEATURE_ON, LATEST_YEAR, ROOT_TYPES } from '$lib/constants';
	import { prettifyRoot } from '$lib/text-format-util';
	import { resultsHidden } from '$lib/stores';

	export let data: {
		surveyShouldPrompt: boolean;
		user: { orcid: string; name: string; semanticId?: string } | null;
		isAdmin: boolean;
		askEmail: boolean;
	};
	const SEARCH_LISTBOX_ID = 'search-listbox';

	let options: RootType[] = ROOT_TYPES;
	let cat: RootType | 'all' = 'all';

	let searchComp: SearchResults;
	let activeIndex = -1;

	let mounted = false;
	let dropdownOpen = false;
	let userMenuOpen = false;
	// let innerWidth = 900;
	let innerWidth: number;

	// Width thresholds for how many type links sit inline before the rest fold into the "More"/"Types"
	// dropdown. All six only fit past ~880px; below that show three, and on phones fold them all away.
	$: visibleCount = innerWidth >= 880 ? options.length : innerWidth >= 620 ? 3 : 0;
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

	async function openSearchFor(opt: RootType | 'all') {
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
		userMenuOpen = false;
		resultsHidden.set(true);
	});

	let searchTerm = '';

	function openFullSearch() {
		const q = searchTerm.trim();
		if (!q) return;
		resultsHidden.set(true);
		goto(`/search?q=${encodeURIComponent(q)}`);
	}

	function keyBind(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			resultsHidden.set(true);
			dropdownOpen = false;
			return;
		}
		if ($resultsHidden) return;
		if (e.key === 'ArrowDown') {
			e.preventDefault();
			searchComp?.move(1);
		} else if (e.key === 'ArrowUp') {
			e.preventDefault();
			searchComp?.move(-1);
		} else if (e.key === 'Enter') {
			e.preventDefault();
			// Open the highlighted result, or fall through to the full /search page.
			if (!searchComp?.openActive()) openFullSearch();
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
<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div id="main-fix">
	<header id="site-header">
		<a href="/" class="header-logo" aria-label="Home">
			<svg viewBox="0 0 20 20">
				<PathLogo />
			</svg>
		</a>

		<nav class="header-nav">
			<button
				class="nav-link search-all"
				class:active={!$resultsHidden && cat === 'all'}
				on:click={() => openSearchFor('all')}
			>
				Search
			</button>

			{#each visibleOptions as opt, __i (__i)}
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
						class:active={!$resultsHidden && cat !== 'all' && overflowOptions.includes(cat)}
						on:click={() => (dropdownOpen = !dropdownOpen)}
					>
						{visibleCount === 0 ? 'Types' : 'More'} &#9662;
					</button>
					{#if dropdownOpen}
						<div class="dropdown-menu" transition:slide={{ duration: 150, axis: 'y' }}>
							{#each overflowOptions as opt, __i (__i)}
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

		<div class="header-auth">
			{#if data.user}
				<div class="dropdown">
					<button
						class="user-btn"
						class:active={userMenuOpen}
						on:click|stopPropagation={() => (userMenuOpen = !userMenuOpen)}
					>
						{data.user.name.split(' ')[0]} &#9662;
					</button>
					{#if userMenuOpen}
						<div class="dropdown-menu user-menu" transition:slide={{ duration: 150, axis: 'y' }}>
							{#if data.user.semanticId}
								<a
									class="dropdown-item"
									href="/authors/{data.user.semanticId}"
									on:click={() => (userMenuOpen = false)}>My Profile</a
								>
							{/if}
							{#if EMAIL_FEATURE_ON}
								<a
									class="dropdown-item"
									href="/email-preferences"
									on:click={() => (userMenuOpen = false)}>Email preferences</a
								>
							{/if}
							{#if data.isAdmin}
								<a class="dropdown-item" href="/admin" on:click={() => (userMenuOpen = false)}
									>Admin</a
								>
							{/if}
							<a
								class="dropdown-item logout-item"
								href="/logout"
								data-sveltekit-preload-data="off"
								on:click={() => (userMenuOpen = false)}>Logout</a
							>
						</div>
					{/if}
				</div>
			{:else}
				<a
					class="login-btn"
					href="/login?returnTo={encodeURIComponent(page.url.pathname + page.url.search)}"
					data-sveltekit-preload-data="off">Login</a
				>
			{/if}
		</div>

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

	{#if data.askEmail}
		<!-- plain GET form: the typed address arrives at /email-preferences as ?email= -->
		<form class="email-banner" action="/email-preferences">
			<span>Get an email when your requested changes go live, or when Rankless has news.</span>
			<input
				name="email"
				type="email"
				placeholder="you@example.org"
				autocomplete="email"
				aria-label="Email address"
			/>
			<button type="submit">Set email preferences</button>
		</form>
	{/if}

	{#if !$resultsHidden}
		<div id="search-bar" transition:slide={{ duration: 200, axis: 'y' }}>
			<input
				bind:value={searchTerm}
				on:focus={focusSelect}
				use:init
				type="text"
				id="search-input"
				role="combobox"
				aria-expanded={!$resultsHidden}
				aria-controls={SEARCH_LISTBOX_ID}
				aria-activedescendant={activeIndex >= 0
					? `${SEARCH_LISTBOX_ID}-opt-${activeIndex}`
					: undefined}
				aria-autocomplete="list"
				autocomplete="off"
			/>
		</div>
	{/if}

	<SearchResults
		bind:this={searchComp}
		bind:activeIndex
		listboxId={SEARCH_LISTBOX_ID}
		{searchTerm}
		{cat}
	/>
	<div
		id="main-content"
		on:click={() => {
			dropdownOpen = false;
			userMenuOpen = false;
		}}
	>
		<slot />
	</div>
	<div id="main-foot">
		<TextedLogo pad={0} size={30} />
		<span>{LATEST_YEAR}</span>
		<div id="foot-r">
			{#if data.user}<a href="/mcp">Developers</a>{/if}<a href="/game">Games</a><a href="/release"
				>Data</a
			><a href="/privacy">Privacy</a><a href="/#contact">Contact</a>
		</div>
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
		font-size: var(--text-base);
		padding: 6px 10px;
		cursor: pointer;
		color: var(--color-theme-darkgrey);
		transition:
			background-color 0.15s,
			color 0.15s;
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

	.search-all {
		font-weight: bold;
		color: var(--color-theme-darkblue);
		border: 1px solid var(--color-theme-darkblue);
		margin-right: 6px;
	}

	.search-all:hover,
	.search-all.active {
		background-color: var(--color-theme-darkblue);
		color: var(--color-theme-white);
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
		font-size: var(--text-base);
		padding: 8px 14px;
		cursor: pointer;
		color: var(--color-theme-darkgrey);
		text-align: left;
		white-space: nowrap;
		transition:
			background-color 0.15s,
			color 0.15s;
	}

	.dropdown-item:hover {
		background-color: var(--color-theme-lightblue);
		color: var(--color-theme-darkblue);
	}

	.dropdown-item.active {
		color: var(--color-theme-darkblue);
		font-weight: bold;
	}

	.header-auth {
		display: flex;
		align-items: center;
		flex-shrink: 0;
		margin-left: auto;
		margin-right: 4px;
	}

	.login-btn {
		font-size: var(--text-sm);
		padding: 5px 10px;
		color: var(--color-theme-darkgrey);
		text-decoration: none;
		border: 1px solid transparent;
		transition:
			background-color 0.15s,
			color 0.15s;
	}

	.login-btn:hover {
		background-color: var(--color-theme-lightblue);
		color: var(--color-theme-darkblue);
	}

	.user-btn {
		background: none;
		border: none;
		font-family: inherit;
		font-size: var(--text-base);
		padding: 5px 10px;
		cursor: pointer;
		color: var(--color-theme-darkgrey);
		transition:
			background-color 0.15s,
			color 0.15s;
		white-space: nowrap;
		max-width: 120px;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.user-btn:hover,
	.user-btn.active {
		background-color: var(--color-theme-lightblue);
		color: var(--color-theme-darkblue);
	}

	.user-menu {
		right: 0;
		left: auto;
	}

	/* user menu uses <a> elements, ensure they look like dropdown buttons */
	.user-menu :global(a.dropdown-item) {
		display: block;
		text-decoration: none;
	}

	.logout-item {
		opacity: 0.6;
	}

	.email-banner {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 8px 12px;
		padding: 10px 3vw;
		background-color: var(--color-theme-lightblue);
		color: var(--color-theme-darkblue);
		font-size: var(--text-sm);
	}

	.email-banner input {
		font: inherit;
		padding: 5px 8px;
		border: 1px solid var(--color-theme-darkblue);
		border-radius: 3px;
		min-width: 220px;
	}

	.email-banner button {
		font: inherit;
		cursor: pointer;
		padding: 5px 12px;
		border: none;
		border-radius: 3px;
		background-color: var(--color-theme-darkblue);
		color: var(--color-theme-white);
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
		top: var(--header-height);
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
		flex-wrap: wrap;
		gap: 0 12px;
		padding-left: 3vw;
		padding-right: 3vw;
		padding-top: 3px;
		padding-bottom: 3px;
		background-color: var(--color-theme-yellow);
		color: var(--color-theme-darkgrey);
		flex: 0 0 auto;
		min-height: 50px;
		z-index: 1;
	}

	#foot-r {
		display: flex;
		flex-wrap: wrap;
		gap: 4px 16px;
	}

	#foot-r > a {
		color: var(--color-theme-darkgrey);
	}
</style>
