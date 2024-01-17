<script lang="ts">
	import { base } from '$app/paths';
	import { goto } from '$app/navigation';
	import { INSTITUTION_TYPE } from '$lib/constants';
	import type { SelectionOption } from '$lib/tree-types';
	import { onMount } from 'svelte';
	import { handleStore } from '$lib/tree-loading';
	import { getTopFzfInsts } from '$lib/search-util';
	import { flowerPaths, thinFlowerPaths } from '$lib/visual-util';
	import HexagonLogo from '$lib/components/HexagonLogo.svelte';
	import Flower from '$lib/components/Flower.svelte';
	import CircleBurst from '$lib/components/CircleBurst.svelte';
	import { formatNumber } from '$lib/text-format-util';

	let instOptions: SelectionOption[] = [];

	onMount(() => {
		handleStore('root-descriptions', (jsv) => {
			// @ts-ignore
			instOptions = jsv[INSTITUTION_TYPE];
		});
	});

	function onChange(e: SelectionOption | undefined) {
		if (e != undefined) {
			goto(`${base}/view/${INSTITUTION_TYPE}/${e.id}`); //TODO this is capitalized!!
		}
	}

	let rotScaler = 1.2;
	let resultsHidden = true;
	let searchTerm = '';
	$: searchResults = getTopFzfInsts(searchTerm, instOptions, 6);

	function onFocus() {
		rotScaler -= 0.9;
		resultsHidden = false;
	}

	function onBlur() {
		rotScaler += 0.9;
		if (searchTerm.length == 0) {
			resultsHidden = true;
		}
	}

	function paginator(rate: number, min: number, max: number) {
		if (min < rate) {
			if (rate < max) {
				return 'current page';
			}
			return 'last page';
		}
		return 'next page';
	}

	let scrollY: number;
	let innerHeight: number;
	let outerHeight: number;
	let clientHeight: number;
	$: scrollRate = scrollY / (clientHeight - innerHeight);
	$: inputWidth = scrollRate > 0 ? 100 : 80;
	$: inputTop = scrollRate > 0 ? 0 : 120;

	// <span style="position: sticky; top: 150px; left: 100px; z-index: 100;">{scrollRate}</span>
</script>

<svelte:window bind:scrollY bind:innerHeight bind:outerHeight />

<div bind:clientHeight id="main-container">
	<!-- text -->
	<div class={paginator(scrollRate, -1, 0.1)}>
		<p id="p-1">
			In a world where every country dreams of becoming a knowledge powerhouse, we need more than
			university rankings.
		</p>
	</div>
	<div class={paginator(scrollRate, 0.1, 0.25)}>
		<p id="p-2">
			Universities are a source of <b>cultural and economic growth</b>. They attract talent, educate
			the population, and help produce important innovations.
		</p>
	</div>
	<div class={paginator(scrollRate, 0.25, 0.4)}>
		<p id="p-3">
			But the impact of universities cannot be reduced to a single number. <b
				>Knowledge is highly specific</b
			>, and so is the impact of universities.
		</p>
	</div>
	<div class={paginator(scrollRate, 0.4, 0.55)}>
		<p id="p-4">
			Universities specialize in <b>fields</b> and local <b>networks of collaboration</b>.
		</p>
	</div>
	<div class={paginator(scrollRate, 0.55, 0.7)}>
		<p id="p-5">Isn’t it time we understand them in their right context?</p>
	</div>
	<div class={paginator(scrollRate, 0.7, 2)}>
		<p id="p-6">
			Academic impact is not a single thing, but a rich kaleidoscope of topics and geographies that
			can be exciting to explore.
		</p>
		<p id="p-7">Go ahead and explore impact beyond rankings, at the academic impact explorer.</p>
	</div>
	<!-- search -->

	<div class="search-results" style="display: {resultsHidden ? 'none' : 'flex'};">
		<span id="result-closer" on:click={() => (resultsHidden = true)}>&#10006;</span>
		{#each searchResults as searchResult}
			<div on:click={() => onChange(searchResult)} class="result-card">
				<h3>
					{searchResult.name}
				</h3>
				<span>{formatNumber(searchResult.papers)} papers</span>
				<span>{formatNumber(searchResult.citations)} citations</span>
			</div>
		{/each}
	</div>

	<input
		bind:value={searchTerm}
		id="top-input"
		on:blur={onBlur}
		on:focus={onFocus}
		placeholder="Search for an Institution!"
		type="text"
		class="search-input"
		style="width: {inputWidth}%; top: {inputTop}px; left: {(100 - inputWidth) / 2}%"
	/>
	<!-- decoration -->

	<div class="bg-bar" id="top-blue">
		<div class="white-line" id="line-1" />
		<div class="white-line" id="line-2" />
		<div class="white-line" id="line-3" />
	</div>

	<div class="bg-bar" id="mid-pink" />

	<div class="bg-bar" id="purp-bar" />

	<div class="bg-bar" id="grey-bar" />

	<svg id="logo-img" viewBox="-3 -3 6 6" xmlns="http://www.w3.org/2000/svg">
		<HexagonLogo {rotScaler} />
	</svg>

	<svg id="thin-flower-img" viewBox="0 -300 1200 1700" xmlns="http://www.w3.org/2000/svg">
		<Flower paths={thinFlowerPaths} width={6} color="var(--color-theme-lightblue)" />
	</svg>

	<svg id="flower-img" viewBox="0 0 800 800" xmlns="http://www.w3.org/2000/svg">
		<Flower paths={flowerPaths} color="var(--color-theme-purple)" />
	</svg>

	<svg id="burst-1" viewBox="-110 -110 900 900" xmlns="http://www.w3.org/2000/svg">
		<CircleBurst />
	</svg>

	<svg id="final-thin-flower" viewBox="-500 -600 1000 1200" xmlns="http://www.w3.org/2000/svg">
		<Flower paths={thinFlowerPaths} width={3} color="var(--color-theme-blue)" />
	</svg>
</div>

<style>
	#main-container {
		height: 800vh;
	}

	.page {
		position: fixed;
		height: 100svh;
		width: 100%;
		transition: 650ms;
	}

	.current {
		top: 0px;
	}

	.next {
		top: 110dvh;
	}

	.last {
		top: -110dvh;
	}

	p {
		margin: auto;
		margin-top: 18svh;
		max-width: 1200px;
		font-size: min(80px, 7vw);
		font-weight: 400;
		padding: 20px;
		text-align: justify;
		line-height: 1.5;
	}

	#p-1 {
		color: var(--color-theme-darkgrey);
		padding-right: 33vw;
	}

	#p-2 {
		color: var(--color-theme-darkblue);
	}

	#p-2 > b {
		color: var(--color-theme-red);
	}

	.search-input {
		transition: all 0.6s;
		position: absolute;
		border-top: solid var(--color-theme-darkblue) 5px;
		background-color: var(--color-theme-lightgrey);
		box-shadow: 7px 7px 22px var(--color-theme-darkgrey);
		height: 40px;
		font-size: 30px;
		z-index: 10;
	}

	input.search-input:focus {
		outline: none;
	}

	.search-results {
		width: 100%;
		height: 100dvh;
		backdrop-filter: blur(6px);
		position: fixed;
		top: 0px;
		z-index: 3;
		flex-direction: columns;
		flex-wrap: wrap;
		justify-content: space-around;
		align-items: start;
		padding-top: 180px;
	}

	.result-card {
		cursor: pointer;
		height: 200px;
		width: 320px;
		min-width: 320px;
		background-color: var(--color-theme-lightblue);
		border: solid var(--color-theme-blue) 4px;
		box-shadow: 10px 10px 40px var(--color-theme-darkgrey);
		border-radius: 10px;
		margin: 40px;
		font-size: xx-large;
		text-align: center;
		flex: 0 0 26%;
		padding: 16px;
	}

	#result-closer {
		position: absolute;
		top: 70px;
		left: 95%;
		font-size: 37px;
		padding: 12px;
		text-align: center;
		border-radius: 35px;
		cursor: pointer;
	}

	#top-input {
		position: fixed;
		text-align: center;
	}

	/* decorations */

	.white-line {
		width: 100%;
		height: 20px;
		position: absolute;
		z-index: -8;
		background-color: var(--color-theme-white);
	}

	#line-1 {
		top: 160px;
	}

	#line-2 {
		top: 300px;
	}

	#line-3 {
		top: 440px;
	}

	.bg-bar {
		position: absolute;
		z-index: -9;
		width: 100%;
	}

	#top-blue {
		height: 80svh;
		top: 0px;
		opacity: 60%;
		background-image: linear-gradient(
			var(--color-theme-lightblue),
			var(--color-theme-blue) 20%,
			var(--color-theme-lightgrey)
		);
	}

	#mid-pink {
		position: absolute;
		height: 70svh;
		opacity: 80%;
		top: 15%;
		background-image: linear-gradient(var(--color-theme-pink), var(--color-theme-lightblue));
	}

	#purp-bar {
		position: absolute;
		height: 90svh;
		width: 75%;
		margin-left: 25%;
		top: 28%;
		background-image: linear-gradient(
			180deg,
			var(--color-theme-pink) 12.5%,
			var(--color-theme-purple) 46%,
			var(--color-theme-purple) 70%,
			rgba(255, 255, 255, 0) 100%
		);
	}

	#grey-bar {
		position: absolute;
		height: 340svh;
		top: 55%;
		background-image: linear-gradient(
			7deg,
			rgba(255, 255, 255, 0),
			rgba(255, 255, 255, 0) 20%,
			var(--color-theme-lightgrey) 30%,
			var(--color-theme-pink) 70%,
			rgba(255, 255, 255, 0) 80%,
			rgba(255, 255, 255, 0) 100%
		);
	}

	svg {
		position: absolute;
		z-index: -5;
	}

	#logo-img {
		width: 40%;
		top: 40px;
		right: 5%;
	}

	#thin-flower-img {
		width: 90%;
		top: 300px;
		left: 0px;
	}

	#burst-1 {
		width: 66%;
		top: 28%;
	}

	#flower-img {
		width: 80%;
		top: 50%;
		left: 4%;
	}

	#final-thin-flower {
		width: 100%;
		bottom: 0px;
		left: 0px;
		opacity: 40%;
	}
</style>
