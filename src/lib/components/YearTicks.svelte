<script lang="ts">
	import { LATEST_YEAR, FONT_SIZE_PX } from '$lib/constants';
	import { getColor } from '$lib/style-util';
	import TickBars from './TickBars.svelte';

	export let bottomStacks: number[];
	export let topStacks: number[];
	export let end: number = LATEST_YEAR;
	export let fullHeight: number;

	let h = 2.55;
	let p = 0.45;

	let rightP = 0.5;
	let topText = ['Indexed', 'citations:'];
	let bottomText = ['Papers:'];
	function maxLen(lArr: string[], rArr: string[]) {
		return lArr.concat(rArr).reduce((l, r) => (l.length > r.length ? l : r)).length;
	}

	//make it 17.5:7 -> 2.5
	$: fullH = (h + p) * 2;
	$: fontSize = (fullH / fullHeight) * FONT_SIZE_PX * 0.8;
	$: leftP = fontSize * 0.8 * maxLen(topText, bottomText);
	$: w = 13.5 - leftP;
	$: fullW = leftP + rightP + w;
	$: iMul = w / bottomStacks.length;
	$: barW = iMul * 0.8;
	$: yearFontSize = fontSize * 0.75;

	let lineW = 0.022;
</script>

{#if fullW != undefined && fullHeight != undefined}
	<svg viewBox="-{leftP} -{h + p} {fullW} {fullH}">
		<TickBars
			nums={bottomStacks}
			color={getColor(0.05)}
			{h}
			{w}
			{barW}
			{fontSize}
			startPad={leftP}
			text={bottomText}
		/>
		<TickBars
			nums={topStacks}
			color={getColor(0.35)}
			{h}
			{w}
			{barW}
			{fontSize}
			flip={true}
			startPad={leftP}
			text={topText}
		/>
		<line
			x1="0"
			y1="0"
			x2={(bottomStacks.length - 1) * iMul}
			y2="0"
			width="0.2"
			stroke="black"
			stroke-width={lineW}
		/>
		{#each bottomStacks.entries() as [i, _]}
			<line x1={i * iMul} x2={i * iMul} y1={-0.1} y2={0.1} stroke-width={lineW} stroke="black" />
		{/each}
		<g transform="rotate(270) translate(0.5, {yearFontSize / 2.75})">
			<text font-size={fontSize * 0.8} text-anchor="start">{end - 10}</text>
			<text font-size={fontSize * 0.8} y={5 * iMul} text-anchor="start">{end - 5}</text>
		</g>
		<!-- <text font-size={fontSize} y="0.05" x="-0.8" text-anchor="end">{end - 10}</text> -->
		<!-- <text font-size={fontSize} y="0.05" x="10.5" text-anchor="start">{end}</text> -->
	</svg>
{/if}

<style>
	svg {
		height: 100%;
		width: 100%;
	}

	text {
		pointer-events: none;
	}
</style>
