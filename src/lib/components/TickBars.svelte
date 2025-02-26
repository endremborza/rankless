<script lang="ts">
	import { HIGH_OP } from '$lib/constants';
	import { formatNumber } from '$lib/text-format-util';
	import { rescale } from '$lib/visual-util';

	export let h: number;
	export let w: number;
	export let nums: number[];
	export let color: string;
	export let text: string[];
	export let lineW: number;
	export let flip: boolean = false;
	export let barW: number = 0.85;
	export let endPad: number = w * 0.15;
	export let startPad: number = w * 0.15;
	export let fontSize: number = barW - 15;

	let vSpace = 1.3;
	let vStart = 1.9;

	function getYs(flip: boolean, fullV: number) {
		const out = [flip ? -vStart : vStart];
		for (let i = 0; i < 5; i++) {
			out.push(out[i] + fullV);
		}
		return out;
	}

	$: fullV = fontSize * vSpace;
	$: scaledConf = rescale(nums, h);
	$: mult = flip ? -1 : 1;
	$: textYs = getYs(flip, fullV);
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

{#if scaledConf.total > 1}
	<g opacity="0.85">
		{#each scaledConf.scaled as [i, y]}
			{#if y > 0}
				<line
					x1={i}
					x2={i}
					y1={0}
					y2={mult * y}
					stroke-width={barW}
					stroke={color}
					opacity={(HIGH_OP - 15) / 100}
				/>
				<!-- <text x={i} {y} font-size="0.2" text-anchor="middle">{bottomScaled.nominal[i]}</text> -->
			{/if}
		{/each}
	</g>
	<g fill={color} font-size={fontSize} transform="translate(-{startPad}, 0)" filter="url(#shadow)">
		<text y={textYs[0]} text-anchor="start" filter="url(#shadow)"
			>{formatNumber(scaledConf.total)}</text
		>
		{#each text.entries() as [i, line]}
			<text y={textYs[i + 1]} text-anchor="start">{line}</text>
		{/each}
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
	<text font-size={fontSize} x={w + endPad} y={mult * h + fontSize / 3} text-anchor="end"
		>{formatNumber(scaledConf.max)}</text
	>
{/if}
