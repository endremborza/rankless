<script lang="ts">
	import { LOW_OP } from '$lib/constants';
	import { formatNumber } from '$lib/text-format-util';
	import { rescale } from '$lib/visual-util';

	export let h: number;
	export let w: number;
	export let nums: number[];
	export let color: string;
	export let text: string[];
	export let flip: boolean = false;
	export let barW: number = 0.85;
	export let startPad: number = w * 0.15;
	export let fontSize: number = barW - 15;

	let vSpace = 1.3;
	let vMid = 1.24;

	function getYs(flip: boolean, fullV: number) {
		let span = text.length * fullV;
		let init = flip ? -vMid : vMid;
		const out = [init - span / 2];
		for (let i = 0; i <= nums.length; i++) {
			out.push(out[i] + fullV);
		}
		return out;
	}

	$: fullV = fontSize * vSpace;
	$: scaledConf = rescale(nums, h);
	$: mult = flip ? -1 : 1;
	$: iMul = w / nums.length;
	$: textYs = getYs(flip, fullV);

	let hoverInfo: { x: number; y: number; text: string } | undefined = undefined;

	function setHover(i: number, y: number) {
		hoverInfo = { x: i * iMul, y: y * mult, text: formatNumber(nums[i]) };
	}
	function loseHover() {
		hoverInfo = undefined;
	}
</script>

<g opacity={LOW_OP / 100}>
	{#each scaledConf.scaled as [i, y] (i)}
		{#if y > 0}
			<line
				x1={i * iMul}
				x2={i * iMul}
				y1={0}
				y2={mult * y}
				stroke-width={barW}
				stroke={color}
				role="none"
				on:mouseover={() => setHover(i, y)}
				on:focus={() => setHover(i, y)}
				on:mouseleave={loseHover}
				on:focusout={loseHover}
				style="filter: drop-shadow(0px 0px 0.15px rgba(220, 220, 220, 0.9));"
			/>
		{/if}
	{/each}
</g>
<g font-size={fontSize} transform="translate(-{startPad}, 0)">
	{#each text.entries() as [i, line] (i)}
		<text y={textYs[i]} text-anchor="start">{line}</text>
	{/each}
	<text y={textYs[text.length]} text-anchor="start">{formatNumber(scaledConf.total)}</text>
</g>
{#if hoverInfo != undefined}
	<text x={hoverInfo.x} y={mult * h} font-size={fontSize} text-anchor="middle"
		>{hoverInfo.text}</text
	>
{/if}
