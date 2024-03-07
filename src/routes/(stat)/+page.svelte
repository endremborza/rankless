<script lang="ts">
	import {flowerPaths, thinFlowerPaths, pinRange} from '$lib/visual-util';
	import HexagonLogo from '$lib/components/HexagonLogo.svelte';
	import Flower from '$lib/components/Flower.svelte';
	import CircleBurst from '$lib/components/CircleBurst.svelte';
	import SearchLogo from '$lib/components/SearchLogo.svelte';
	import ScrollyCGraph from '$lib/components/ScrollyCGraph.svelte';
	import ScrollySank from '$lib/components/ScrollySank.svelte';
	import SearchResults from '$lib/components/SearchResults.svelte';

	let rotScaler = 1.2;
	let resultsHidden = true;
	let searchTerm = '';

	function onFocus() {
		rotScaler -= 0.9;
		resultsHidden = false;
	}

	function onBlur() {
		rotScaler += 0.9;
		if (searchTerm.length == 0) {
			// resultsHidden = true;
		}
	}

	function getInputSpecs(scrollRate: number): [number, number, number] {
		if (scrollRate == 0) {
			return [45, 5, 20];
		}
		if (scrollRate < 9) {
			return [100, 0, 0];
		}
		return [60, 80, 10];
	}

	let scrollY: number;
	let innerHeight: number;
	let outerHeight: number;
	let innerWidth: number;

	$: sHeight = innerHeight || 2000;
	$: sWidth = innerWidth || 2000;
	$: isWideScreen = sWidth / sHeight > 1.2;
	$: [inputWidth, inputTop, inLeft] = getInputSpecs(scrollY / sHeight);

	const inHeight = 58;

	$: ratePin = (srate: number, erate: number, osrate: number) =>
		pinRange(scrollY, sHeight * srate, sHeight * erate, sHeight * osrate);
	$: rateScale = (srate: number, frate: number) =>
		Math.max(0, Math.min((scrollY / sHeight - srate) / frate, 1));
	$: p2Top = ratePin(1.2, 2.5, 0.3);
</script>

<svelte:window bind:scrollY bind:innerHeight bind:outerHeight bind:innerWidth />

<div id="main-container" style="--pwidth: {isWideScreen ? '38%' : '90%'}">
	<!-- text -->
	<p id="p-1" style="top: {ratePin(0, 0.7, 0.15)}px;">
		In a world, where every country dreams of becoming a knowledge powerhouse, we need more than
		university rankings.
	</p>
	<p id="p-2" style="top: {p2Top}px;">
		Universities are a source of <b>cultural and economic growth</b>. They attract talent, educate
		the population, and help produce important innovations.
	</p>
	<p id="p-3" style="top: {ratePin(4, 4.7, 0.2)}px;">
		But the impact of universities cannot be reduced to a single number. <b>Knowledge is highly
			specific</b>, and so is the impact of universities.
	</p>
	<p id="p-4" style="top: {ratePin(5.3, 5.9, 0.4)}px;">
		Universities specialize in <b>fields</b> and local <b>networks of collaboration</b>.
		<span id="inner-4" style="opacity: {rateScale(5.3, 0.4) * 100}%">
			Isn’t it time we understand them in their right context?
		</span>
	</p>
	<p id="p-5" style="top: {ratePin(6.4, 8.5, 0.4)}px; width: 36%">
		Take the work done by Oregon State University. Instead of looking at them as one element of a
		list of Universities of varied focuses, sizes and locations, you can visualize how papers
		relating to <b id="geol">geology</b> or <b id="geog">geography</b>, are citing articles
		published by authors affiliated with Oregon State around the globe.
	</p>

	<p id="p-6" style="top: {ratePin(9.1, 9.8, 0.2)}px;">
		Academic impact is not a single thing, but a rich kaleidoscope of topics and geographies that
		can be exciting to explore.
	</p>
	<p id="p-7" style="top: {ratePin(9.7, 10.5, 0.4)}px;">
		Go ahead and explore impact beyond rankings!
	</p>
	<!-- graphs -->
	<ScrollyCGraph {scrollY} {sHeight} {ratePin} {isWideScreen} />
	<ScrollySank {sWidth} {sHeight} {ratePin} {rateScale} {isWideScreen} />
	<!-- search -->

	<SearchResults bind:resultsHidden {searchTerm} />

	<input bind:value={searchTerm} on:blur={onBlur} on:focus={onFocus} placeholder="Explore an Institution!"
		type="text" class="search-input"
		style="width: {inputWidth}%; top: {inputTop}svh; left: {inLeft}%; height: {inHeight}px" />

	<svg width={inHeight} height={inHeight} viewBox="-10 -10 50 50" fill="none" xmlns="http://www.w3.org/2000/svg"
		style="z-index: 11; top: {inputTop}svh; left: {inLeft}%; transition: all 0.6s; position: fixed">
		<SearchLogo />
	</svg>
	<!-- decoration -->

	<div class="bg-bar" id="top-blue">
		{#each [...Array(8).keys()].map((x) => 155 + x * 50) as topOff}
		<div class="white-line" style="top: {topOff}px" />
		{/each}
	</div>

	<div class="bg-bar" id="mid-pink" />

	<div class="bg-bar" id="purp-bar" />

	<div class="bg-bar" id="grey-bar" />

	<svg id="logo-img" viewBox="-2.5 -2 4.9 5.3" xmlns="http://www.w3.org/2000/svg"
		style="opacity: {innerWidth > innerHeight ? 70 : 0}%;">
		<HexagonLogo {rotScaler} />
	</svg>

	<svg id="thin-flower-img" viewBox="0 -150 1000 1700" xmlns="http://www.w3.org/2000/svg">
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
		height: 1100svh;
	}

	p {
		font-size: min(5svh, 7vw);
		font-weight: 400;
		line-height: 1.5;
		position: absolute;
		z-index: 6;
		width: var(--pwidth);
	}

	#p-1 {
		color: var(--color-theme-darkblue);
		font-weight: 600;
		left: 40px;
	}

	#p-2 {
		color: var(--color-theme-darkblue);
		text-align: right;
		right: 40px;
	}

	#p-2>b {
		color: var(--color-theme-red);
	}

	#p-3 {
		left: 5%;
	}

	#p-4 {
		right: 5%;
		text-align: right;
	}

	#p-5 {
		right: 8%;
		padding: 2vw;
		font-size: min(3svh, 5vw);
		background: var(--color-theme-pink);
		border: solid var(--color-theme-blue) 8px;
	}

	#p-6 {
		left: 8%;
	}

	#p-7 {
		right: 9%;
		text-align: right;
	}

	#geol {
		color: rgb(var(--color-range-25));
	}

	#geog {
		color: rgb(var(--color-range-75));
	}

	#inner-4 {
		color: var(--color-theme-darkblue);
	}

	.search-input {
		transition: all 0.6s;
		padding-left: 80px;
		position: fixed;
		border-top: solid var(--color-theme-darkblue) 5px;
		border-radius: 6px;
		background-color: var(--color-theme-lightgrey);
		box-shadow: 7px 7px 17px var(--color-theme-darkgrey);
		font-size: 40px;
		z-index: 10;
	}

	input.search-input:focus {
		outline: none;
	}

	/* decorations */

	.white-line {
		width: 100%;
		height: 7px;
		position: absolute;
		z-index: -8;
		background-color: var(--color-theme-white);
		opacity: 80%;
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
		background-image: linear-gradient(var(--color-theme-lightblue),
				var(--color-theme-blue) 20%,
				var(--color-theme-lightgrey));
	}

	#mid-pink {
		position: absolute;
		height: 70svh;
		opacity: 80%;
		top: 120svh;
		background-image: linear-gradient(var(--color-theme-pink), var(--color-theme-lightblue));
	}

	#purp-bar {
		position: absolute;
		height: 90svh;
		width: 75%;
		margin-left: 25%;
		top: 350svh;
		background-image: linear-gradient(180deg,
				var(--color-theme-pink) 12.5%,
				var(--color-theme-purple) 46%,
				var(--color-theme-purple) 70%,
				rgba(255, 255, 255, 0) 100%);
	}

	#grey-bar {
		position: absolute;
		height: 340svh;
		top: 460svh;
		background-image: linear-gradient(7deg,
				rgba(255, 255, 255, 0),
				rgba(255, 255, 255, 0) 20%,
				var(--color-theme-lightgrey) 30%,
				var(--color-theme-pink) 70%,
				rgba(255, 255, 255, 0) 80%,
				rgba(255, 255, 255, 0) 100%);
	}

	svg {
		position: absolute;
		z-index: -5;
	}

	#logo-img {
		height: 70svh;
		top: 10%;
		transition: opacity 200ms linear;
		right: 0px;
	}

	#thin-flower-img {
		width: min(1333px, 100%);
		top: 550px;
		left: 0px;
		z-index: -6;
	}

	#burst-1 {
		width: 66%;
		top: 3000px;
	}

	#flower-img {
		width: 80%;
		top: 870svh;
		left: 4%;
	}

	#final-thin-flower {
		height: 105.5svh;
		/* WHY? the height should match main-container height*/
		width: 100%;
		top: 1000svh;
		left: 0px;
		opacity: 40%;
	}
</style>
