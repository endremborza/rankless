<script lang="ts">
	import { LATEST_YEAR } from '$lib/constants';
	import { getColor } from '$lib/style-util';
	import TickBars from './TickBars.svelte';

	export let bottomStacks: number[];
	export let topStacks: number[];
	export let end: number = LATEST_YEAR;

	let h = 3.25;
	let p = 0.35;

	let w = 10;
	let leftP = 5.5;
	let rightP = 2.5;
	let fontSize = 0.7;

	//make it 17.5:7 -> 2.5
	$: fullW = leftP + rightP + w;
	$: fullH = (h + p) * 2;

	let lineW = 0.022;
	let barW = fontSize + 0.15;
</script>

<svg viewBox="-{leftP} -{h + p} {fullW} {fullH}">
	<TickBars
		nums={bottomStacks}
		color={getColor(0.15)}
		{h}
		{w}
		{lineW}
		{barW}
		{fontSize}
		text={'papers'}
	/>
	<TickBars
		nums={topStacks}
		color={getColor(0.65)}
		{h}
		{w}
		{lineW}
		{barW}
		{fontSize}
		flip={true}
		text={'citations'}
	/>
	<line x1="0" y1="0" x2="10" y2="0" width="0.2" stroke="black" stroke-width={lineW} />
	{#each Array(w).entries() as [i, _]}
		<line x1={i} x2={i} y1={-0.1} y2={0.1} stroke-width={lineW} stroke="black" />
	{/each}
	<g transform="rotate(270) translate(0.5, {fontSize / 2.75})">
		<text font-size={fontSize} text-anchor="start">{end - 10}</text>
		<text font-size={fontSize} y="5" text-anchor="start">{end - 5}</text>
	</g>
	<!-- <text font-size={fontSize} y="0.05" x="-0.8" text-anchor="end">{end - 10}</text> -->
	<!-- <text font-size={fontSize} y="0.05" x="10.5" text-anchor="start">{end}</text> -->
</svg>

<style>
	svg {
		height: 100%;
		width: 100%;
	}
</style>
