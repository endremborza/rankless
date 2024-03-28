<script lang="ts">
	import { flowerPaths, thinFlowerPaths } from '$lib/visual-util';
	import HexagonLogo from '$lib/components/HexagonLogo.svelte';
	import Flower from '$lib/components/Flower.svelte';
	import CircleBurst from '$lib/components/CircleBurst.svelte';
	import ScrollyCGraph from '$lib/components/ScrollyCGraph.svelte';
	import ScrollySank from '$lib/components/ScrollySank.svelte';

	let scrollYRaw: number;
	let innerHeight: number;
	let outerHeight: number;
	let innerWidth: number;

	let minInHeight = 100000;

	function updateInHeight(newHeight: number) {
		if (newHeight < minInHeight) {
			minInHeight = newHeight;
		}
		return minInHeight;
	}

	$: scrollY = scrollYRaw;
	$: sHeight = updateInHeight(innerHeight);
	$: sWidth = innerWidth || 2000;
	$: isWideScreen = sWidth / sHeight > 1.2;
	$: rotScaler = scrollY / 1000 + 1.2;

	function getFixVhFun(height: number, scroll: number) {
		return (start_vh: number, end_vh: number, offset_vh: number) => {
			const scrolled_svh = (scroll / height) * 100;

			let onum = offset_vh;

			if (scrolled_svh < start_vh) {
				onum += start_vh - scrolled_svh;
			} else if (scrolled_svh > end_vh) {
				onum += end_vh - scrolled_svh;
			}
			return `${onum}svh`;
		};
	}

	$: fixedPin = getFixVhFun(sHeight, scrollY);
	$: rateScale = (srate: number, frate: number) =>
		Math.max(0, Math.min((scrollY / sHeight - srate) / frate, 1));
</script>

<svelte:window bind:scrollY={scrollYRaw} bind:innerHeight bind:outerHeight bind:innerWidth />

<div id="main-container" style="--pwidth: {isWideScreen ? '38%' : '90%'}">
	<!-- text -->
	<p id="p-1" style="opacity: {100 - rateScale(0, 0.2) * 100}%;">
		In a world, where every country dreams of becoming a knowledge powerhouse, we need more than
		university rankings.
	</p>
	<p
		id="p-2"
		style="top: {fixedPin(50, 140, 30)}; opacity: {isWideScreen
			? 100
			: 100 - rateScale(0.6, 0.22) * 100}%"
	>
		Universities are a source of <b>cultural and economic growth</b>. They attract talent, educate
		the population, and help produce important innovations.
	</p>
	<p
		id="p-3"
		style="top: {fixedPin(isWideScreen ? 245 : 215, 310, 20)};{isWideScreen ? '' : 'width: 80%'}"
	>
		But the impact of universities cannot be reduced to a single number. <b
			>Knowledge is highly specific</b
		>, and so is the impact of universities.
	</p>
	<p
		id="p-4"
		style="top: {fixedPin(340, 420, 40)};opacity: {100 - rateScale(4.2, 0.2) * 100}%;{isWideScreen
			? ''
			: 'width: 75%'}"
	>
		Universities specialize in <b>fields</b> and local <b>networks of collaboration</b>.
		<span id="inner-4" style="opacity: {rateScale(3.4, 0.2) * 100}%">
			Isn’t it time we understand them in their right context?
		</span>
	</p>
	<p
		id="p-5"
		style="top: {fixedPin(
			500,
			isWideScreen ? 650 : 600,
			isWideScreen ? 40 : 60
		)}; width: {isWideScreen ? 38 : 82}%"
	>
		Take the work done by Oregon State University. Instead of looking at them as one element of a
		list of Universities of varied focuses, sizes and locations, you can visualize how papers
		relating to <b id="geol">geology</b> or <b id="geog">geography</b>, are citing articles
		published by authors affiliated with Oregon State around the globe.
	</p>

	<p id="p-6" style="top: {fixedPin(710, 780, 20)};">
		Academic impact is not a single thing, but a rich kaleidoscope of topics and geographies that
		can be exciting to explore.
	</p>
	<!-- TODO: cut off and make the end somewhat shorter -->
	<p id="p-7" style="top: {isWideScreen ? 40 : 60}svh;opacity: {rateScale(6.9, 0.2) * 100}%">
		Go ahead and explore impact beyond rankings!
	</p>
	<!-- graphs -->
	<ScrollyCGraph {scrollY} {sHeight} topOffset={fixedPin(120, 160, 8)} {isWideScreen} />
	<ScrollySank {sWidth} {sHeight} {fixedPin} {rateScale} {isWideScreen} />

	<!-- decoration -->
	<div class="bg-bar" id="top-blue" />
	{#each [...Array(7).keys()].map((x) => 22 + x * 3.75 * (2 - (scrollY / sHeight) * 4)) as topOff}
		<div class="white-line" style="top: {topOff}svh" />
	{/each}
	<div class="bg-bar" id="mid-pink" />
	<div class="bg-bar" id="purp-bar" />
	<div class="bg-bar" id="grey-bar" />

	<svg
		id="logo-img"
		viewBox="-2.5 -2 4.9 5.3"
		xmlns="http://www.w3.org/2000/svg"
		style="opacity: {innerWidth > innerHeight ? 70 : 0}%;"
	>
		<HexagonLogo {rotScaler} />
	</svg>

	<svg id="thin-flower-img" viewBox="0 -150 1000 1700" xmlns="http://www.w3.org/2000/svg">
		<g style="transform: rotate({scrollY / 88}deg) scaleX({scrollY / sHeight / 2 + 1})"> /* scrolly let to rotate the svg */
			<Flower paths={thinFlowerPaths} width={6} color="var(--color-theme-lightblue)" />
		</g>
		
	</svg>

	<svg id="flower-img" viewBox="0 0 800 800" xmlns="http://www.w3.org/2000/svg">
		<Flower paths={flowerPaths} color="var(--color-theme-purple)" />
	</svg>

	<svg id="burst-1" viewBox="-115 -115 900 900" xmlns="http://www.w3.org/2000/svg">
		<CircleBurst />
	</svg>

	<svg id="final-thin-flower" viewBox="-500 -600 1000 1200" xmlns="http://www.w3.org/2000/svg">
		<Flower paths={thinFlowerPaths} width={3} color="var(--color-theme-blue)" />
	</svg>
</div>

<style>
	#main-container {
		height: 850svh;
	}

	p {
		padding: 0px;
		margin: 0px;
		font-size: min(5svh, 7vw);
		font-weight: 400;
		line-height: 1.5;
		position: fixed;
		z-index: 6;
		width: var(--pwidth);
	}

	#p-1 {
		position: absolute;
		top: 19svh;
		color: var(--color-theme-darkblue);
		font-weight: 600;
		left: 40px;
	}

	#p-2 {
		color: var(--color-theme-darkblue);
		text-align: right;
		right: 40px;
		/* padding-bottom: 20px; */
	}

	#p-2 > b {
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
		color: var(--color-theme-darkgrey3);
		right: 7%;
		padding: 2vw;
		font-size: min(3svh, 5vw);
		backdrop-filter: blur(12px);
		-webkit-backdrop-filter: blur(12px);
		border: solid var(--color-theme-blue) 2px;
		border-radius: 10px;
	}

    #p-6 {
        left: 8%;
        font-size: 3.9em; /* Decrease the font size */
        line-height: 1.1; /* Decrease the line height */
        position: relative; /* Position relative to allow positioning of the pseudo-element */
		background: rgb(255,255,255);
    	background: linear-gradient(180deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0) 50%, rgba(255,255,0,1) 50%, rgba(255,255,0,1) 100%);
        color: black; /* Set the text color */
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

	/* decorations */

	.white-line {
		width: 100%;
		height: min(2.5svh, 3.5vw);
		opacity: 20%;
		position: absolute;
		z-index: -8;
		background-color: var(--color-theme-white);
		opacity: 20%;
	}

	.bg-bar {
		position: absolute;
		z-index: -9;
		width: 100%;
	}

	#top-blue {
		height: 120svh;
		top: 0svh;
		opacity: 60%;
		background-image: linear-gradient(
			var(--color-theme-lightblue),
			var(--color-theme-blue) 20%,
			var(--color-theme-lightgrey)
		);
	}

	#mid-pink {
		height: 70svh;
		opacity: 80%;
		top: 100svh;
		background-image: linear-gradient(var(--color-theme-pink), var(--color-theme-lightblue));
	}

	#bonus-bar {
		height: 70svh;
		opacity: 10%;
		top: 190svh;
		background-color: black;
	}

	#purp-bar {
		height: 90svh;
		/* width: min(75%, 600px); 
		min-width: 600px*/
		width: 75%;
		margin-left: 25%;
		top: 350svh;
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
		top: 460svh;
		background-image: linear-gradient(
			0deg,
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
		height: 70svh;
		top: 10%;
		transition: opacity 200ms linear;
		right: 0px;
	}

	#thin-flower-img {
		width: min(1333px, 100%);
		top: 550px;
		left: 0px;
		opacity: 30%;
		z-index: -6;
	}

	#burst-1 {
		width: 66%;
		top: 360svh;
	}

	#flower-img {
		width: 80%;
		top: 670svh;
		left: 4%;
	}

	#final-thin-flower {
		height: 105.5svh;
		/* WHY? the height should match main-container height*/
		width: 100%;
		left: 0px;
		top: 755svh;
		position: absolute;
		opacity: 40%;
	}
	@keyframes fadeIn {
		from {
			opacity: 1;
		}
		to {
			opacity: 2;
		}
	}
</style>
