<script lang="ts">
	import { formatNumber } from '$lib/text-format-util';
	import { rescale } from '$lib/visual-util';

	export let h: number;
	export let w: number;
	export let nums: number[];
	export let color: string;
	export let text: string;
	export let lineW: number;
	export let flip: boolean = false;
	export let barW: number = 0.85;
	export let fontSize: number = barW - 15;

	let vSpace = 1.3;
	let vStart = 1.8;

	$: fullV = fontSize * vSpace;
	$: scaledConf = rescale(nums, h);
	$: mult = flip ? -1 : 1;
	$: textYs = flip ? [-vStart, -vStart + fullV] : [vStart, vStart + fullV];
</script>

<filter id="shadow" color-interpolation-filters="sRGB">
	<feDropShadow
		dx="0.05"
		dy="0.05"
		stdDeviation="0.02"
		flood-opacity="0.4"
		flood-color="var(--color-theme-shadow)"
	/>
</filter>

<g opacity="0.85">
	{#each scaledConf.scaled as [i, y]}
		{#if y > 0}
			<line x1={i} x2={i} y1={0} y2={mult * y} stroke-width={barW} stroke={color} />
			<!-- <text x={i} {y} font-size="0.2" text-anchor="middle">{bottomScaled.nominal[i]}</text> -->
		{/if}
	{/each}
</g>
<g fill={color} font-size={fontSize} transform="translate(-1.2, 0)" filter="url(#shadow)">
	<text y={textYs[0]} text-anchor="end" filter="url(#shadow)">{formatNumber(scaledConf.total)}</text
	>
	<text y={textYs[1]} text-anchor="end">{text}</text>
</g>
<line
	x1="-0.5"
	y1={mult * h}
	x2={w}
	y2={mult * h}
	stroke-dasharray=".3"
	stroke-width={lineW}
	stroke="black"
/>
<text font-size={fontSize} x="10.5" y={mult * h + fontSize / 3} text-anchor="start"
	>{formatNumber(scaledConf.max)}</text
>
