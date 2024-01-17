<script lang="ts">
	import { getColorArr } from '$lib/style-util';
	import type { NamedNode } from '$lib/tree-types';
	import BrokenFittedText from './BrokenFittedText.svelte';
	import { fade } from 'svelte/transition';

	export let data: NamedNode;
	export let maxPad = 10;
	export let width = 1000;
	export let height = 1000;
	export let combined = false;
	export let colorStart = 0;
	export let colorEnd = 1;
	export let transitionMs = 400;
	export let edgePad = 0.08;

	$: childVals = Object.values(data.children || {});
	$: sumW = childVals?.reduce((l, r) => l + r.weight, 0);
	$: pad = combined ? 0 : maxPad;

	function getColorRate(i: number, combined: boolean) {
		if (combined) {
			return (colorStart + colorEnd) / 2;
		}
		return colorStart + (colorEnd - colorStart) * (i / childVals.length);
	}

	function bsp(
		subc: NamedNode[],
		offsets: number[],
		sizes: number[],
		sumWeight: number,
		offsetIndex: number,
		flats: { name: string; offsets: number[]; sizes: number[] }[],
		pad: number
	) {
		if (subc.length == 1) {
			const tureSizes = sizes.map((x) => x - pad);
			if (Math.min(...tureSizes) > 0) {
				flats.push({
					name: subc[0].name,
					offsets: offsets.map((x) => x + pad),
					sizes: tureSizes
				});
			}
			return flats;
		}
		let preSideSumWeight = subc[0].weight;
		let i = 1;
		let e;
		while (i < subc.length - 1) {
			e = subc[i];
			preSideSumWeight += e.weight;
			i++;
			if (preSideSumWeight > sumWeight / 2) {
				break;
			}
		}

		const preSideSumSize = (preSideSumWeight / sumWeight) * sizes[offsetIndex];

		const valAdder = (arr: number[], addval: number) =>
			arr.map((v, _i) => (_i == offsetIndex ? v + addval : v));

		const postOffsets = valAdder(offsets, preSideSumSize);
		const postSizes = valAdder(sizes, -preSideSumSize);
		const preSizes = valAdder(sizes, preSideSumSize - sizes[offsetIndex]);
		const newOffsetIndex = (offsetIndex + 1) % offsets.length;
		const bcall = (slice, osets, sizes, w) =>
			bsp(slice, osets, sizes, w, newOffsetIndex, flats, pad);
		if (i > 0) {
			bcall(subc.slice(0, i), offsets, preSizes, preSideSumWeight);
		}
		if (i < subc.length) {
			bcall(subc.slice(i), postOffsets, postSizes, sumWeight - preSideSumWeight);
		}
		return flats;
	}

	$: flats = bsp(childVals || [], [0, 0], [width, height], sumW, 0, [], pad);
</script>

<g style="--transition-ms: {transitionMs}ms;">
	{#each flats as node, i}
		<rect
			x={node.offsets[0]}
			y={node.offsets[1]}
			width={node.sizes[0]}
			height={node.sizes[1]}
			style="--crgb: {getColorArr(getColorRate(i, combined))}"
		/>
	{/each}
</g>

{#if !combined}
	<g transition:fade={{ duration: transitionMs }}>
		{#each flats as node}
			<BrokenFittedText
				text={node.name}
				width={node.sizes[0] * (1 - 2 * edgePad)}
				height={node.sizes[1] * (1 - 2 * edgePad)}
				x={node.offsets[0] + node.sizes[0] * edgePad}
				y={node.offsets[1] + node.sizes[1] * (1 - edgePad)}
			/>
		{/each}
	</g>
{:else}
	<g transform="translate(0, {height})" transition:fade={{ duration: transitionMs }}>
		<BrokenFittedText text={data.name} {width} {height} />
	</g>
{/if}

<style>
	rect {
		border: 30px solid black;
		fill: rgba(var(--crgb), 0.6);
		transition: var(--transition-ms);
	}
</style>
