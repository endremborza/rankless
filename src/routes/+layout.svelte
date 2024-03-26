<script lang="ts">
	import { APP_NAME } from '$lib/constants';
	import { base } from '$app/paths';
	import './styles.css';
	import TextedLogo from '$lib/components/TextedLogo.svelte';
	import SearchLogo from '$lib/components/SearchLogo.svelte';
	import SearchResults from '$lib/components/SearchResults.svelte';
	import { afterNavigate } from '$app/navigation';
	import { onMount } from 'svelte';
	import { parse } from 'platform';
	import { fade } from 'svelte/transition';

	let hPen = 0;

	let uInfo: { product?: string } = {};

	onMount(() => {
		uInfo = parse(navigator.userAgent);
		if (uInfo.product == 'iPhone' || uInfo.product == 'iPad') {
			hPen = 10;
		}
	});
	function onFocus() {
		resultsHidden = false;
	}

	function setSizes(hidden: boolean, w: number, slim: boolean) {
		if (slim) {
			headPad = 12;
			headRightWidth = inHeight + 2;
			placeholder = '';
			inLeftPad = inHeight + 2;
			if (hidden) {
				inRight = headRightWidth + headPad + 4;
				inputWidth = 0;
			} else {
				inputWidth = w - 4 - inLeftPad;
				inRight = 2;
			}
		} else {
			inRight = headRightWidth + headPad;
			inLeftPad = baseInLeftPad;
			headPad = basePad;
			headRightWidth = baseRightWidth;
			placeholder = basePlaceholder;
			if (hidden) {
				inputWidth = baseInW;
			} else {
				inputWidth = w - inRight * 2;
			}
		}
	}

	function toggleOpen() {
		slimOpened = !slimOpened;
	}

	afterNavigate(() => {
		slimOpened = false;
		resultsHidden = true;
	});

	const baseInW = 420;
	const basePlaceholder = 'Explore an Institution';
	const basePad = 42;
	const baseRightWidth = 220;
	const baseInLeftPad = 60;

	const year = new Date().getFullYear();

	let innerWidth: number;

	let inHeight = 51;
	let headPad = basePad;
	let inputWidth = baseInW;
	let headRightWidth = baseRightWidth;
	let placeholder = basePlaceholder;
	let inLeftPad = baseInLeftPad;
	let inRight = headRightWidth + headPad;
	let slimOpened = false;

	let resultsHidden = true;
	let searchTerm = '';

	$: isSlim = innerWidth < baseInW * 2;
	$: setSizes(resultsHidden, innerWidth, isSlim);
</script>

<svelte:head>
	<link rel="preconnect" href="https://fonts.googleapis.com" />
	<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
	<link
		href="https://fonts.googleapis.com/css2?family=Roboto+Mono&family=Roboto:ital,wght@0,300;0,400;0,500;0,700;1,300;1,400;1,500;1,700&display=swap"
		rel="stylesheet"
	/>
	<title>{APP_NAME}</title>
</svelte:head>

<svelte:window bind:innerWidth />
{#if innerWidth != undefined}
	<!-- svelte-ignore a11y-click-events-have-key-events -->
	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<div id="main-fix" transition:fade={{ duration: 100 }}>
		<div id="main-head">
			<TextedLogo pad={headPad} />
			<SearchResults bind:resultsHidden {searchTerm} />
			<input
				bind:value={searchTerm}
				on:focus={onFocus}
				{placeholder}
				type="text"
				class="search-block"
				id="search-input"
				style="padding-left: {inLeftPad}px;height: {inHeight -
					hPen}px; right: {inRight}px; width: {inputWidth}px"
			/>

			<svg
				class="search-block"
				id="search-logo"
				width={inHeight}
				height={inHeight}
				viewBox="-10 -10 60 50"
				fill="none"
				xmlns="http://www.w3.org/2000/svg"
				style="right: {inRight + inputWidth + inLeftPad - inHeight}px;"
			>
				<SearchLogo />
			</svg>
			<div id="head-r" style="width: {headRightWidth}px; padding-right: {headPad}px">
				{#if isSlim}
					<svg
						id="slim-stripes"
						viewBox="-2 -2 22 22"
						width={inHeight}
						height={inHeight - 8}
						on:click={toggleOpen}
					>
						{#each [3, 9, 15] as sp}
							<path d="M1,{sp}h16" stroke="var(--color-theme-darkgrey)" stroke-width="1.5px" />
						{/each}
					</svg>
					{#if slimOpened}
						<div id="slim-drop">
							<a href={`${base}/about`}>About</a>
							<a href={`${base}/methods`}>Methods</a>
						</div>
					{/if}
				{:else}
					<a href={`${base}/about`}>About</a>
					<a href={`${base}/methods`}>Methods</a>
				{/if}
			</div>
		</div>
		<div
			id="main-content"
			on:click={() => {
				slimOpened = false;
			}}
		>
			<slot />
		</div>
		<div id="main-foot">
			<div id="foot-r">{APP_NAME} by CCL @ {year}</div>
		</div>
	</div>
{/if}

<style>
	a {
		text-decoration: none;
		color: var(--color-theme-darkgrey);
	}

	#main-fix {
		margin-top: 60px;
		display: flex;
		flex-flow: column;
		height: 100%;
	}

	#main-head {
		position: fixed;
		top: 0px;
		width: 100%;
		display: flex;
		justify-content: space-between;
		/* background-color: rgba(var(--color-range-15), 0.55); */
		background-color: var(--color-theme-yellow);
		z-index: 10;
	}

	#main-content {
		flex: 1 1 auto;
	}

	#main-foot {
		display: flex;
		align-items: center;
		justify-content: center;
		padding-left: 3vw;
		padding-right: 3vw;
		padding-top: 15px;
		padding-bottom: 15px;
		flex: 0 0 70px;
		background-color: var(--color-theme-yellow);
		z-index: 10;
	}

	#foot-r {
		color: var(--color-theme-darkgrey);
	}

	#head-r {
		padding: 8px;
		padding-right: 40px;
		display: flex;
		align-items: center;
		justify-content: end;
	}

	#head-r > a {
		margin-left: 10px;
	}

	#head-r a:hover {
		color: var(--color-theme-darkblue);
		font-weight: bold;
	}

	#slim-stripes {
		cursor: pointer;
	}

	#slim-drop {
		position: fixed;
		right: 0px;
		top: 60px;
		width: 93px;
		height: 120px;
		display: flex;
		flex-direction: column;
		justify-content: space-around;
		padding: 12px;
		padding-left: 20px;
		background-color: var(--color-theme-yellow);
	}

	.search-block {
		position: fixed;
		top: 0px;
		transition: all 0.6s;
	}

	#search-logo {
		pointer-events: none;
		z-index: 13;
	}

	#search-input {
		border-top: solid var(--color-theme-darkblue) 7px;
		border-right: 0px;
		border-left: 0px;
		border-bottom: 0px;
		border-radius: 0px;
		background-color: rgba(255, 255, 255, 0.7);
		font-size: 24px;
		font-style: italic;
		z-index: 11;
		text-indent: 25px;
	}

	#search-input:hover {
		border-top-color: var(--color-theme-white);
		background-color: rgba(171, 171, 171, 0.8);
		color: white;
	}

	input#search-input:focus {
		outline: none;
	}
</style>
