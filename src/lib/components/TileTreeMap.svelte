<script lang="ts">
	import { getColorArr } from '$lib/style-util';
	import type { NamedNode } from '$lib/tree-types';
	import BrokenFittedText from './BrokenFittedText.svelte';
	import TileTreeMap from './TileTreeMap.svelte';

	let {
		data,
		maxPad = 10,
		width = 1000,
		height = 1000,
		xOffset = 0,
		yOffset = 0,
		colorStart = 0,
		colorEnd = 1,
		transitionMs = 400,
		edgePad = 0.08,
		expandedChild = undefined,
		openChildren = [],
		open = true,
		showText = false
	}: {
		data: NamedNode;
		maxPad?: number;
		width?: number;
		height?: number;
		xOffset?: number;
		yOffset?: number;
		colorStart?: number;
		colorEnd?: number;
		transitionMs?: number;
		edgePad?: number;
		expandedChild?: string | undefined;
		openChildren?: string[];
		open?: boolean;
		showText?: boolean;
	} = $props();

	const childVals = $derived(Object.values(data.children || {}));
	const sumW = $derived(childVals?.reduce((l, r) => l + r.weight, 0));
	const pad = $derived(open ? maxPad : 0);
	const colorStep = $derived((colorEnd - colorStart) / childVals.length);
	const theOne = (n: { name: string }, baseVal: number, expVal: number, disposedVal: number) =>
		expandedChild === undefined ? baseVal : expandedChild == n.name ? expVal : disposedVal;

	function bsp(
		subc: NamedNode[],
		offsets: number[],
		sizes: number[],
		sumWeight: number,
		offsetIndex: number,
		flats: { name: string; data: NamedNode; offsets: number[]; sizes: number[] }[],
		pad: number
	) {
		if (subc.length == 0) {
			return [];
		}
		if (subc.length == 1) {
			const trueSizes = [sizes[0] - pad, sizes[1] - pad];
			if (Math.min(...trueSizes) > 0) {
				flats.push({
					name: subc[0].name,
					data: subc[0],
					offsets: [offsets[0] + pad, offsets[1] + pad],
					sizes: trueSizes
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
		const bcall = (slice: NamedNode[], osets: number[], sizes: number[], w: number) =>
			bsp(slice, osets, sizes, w, newOffsetIndex, flats, pad);
		if (i > 0) {
			bcall(subc.slice(0, i), offsets, preSizes, preSideSumWeight);
		}
		if (i < subc.length) {
			bcall(subc.slice(i), postOffsets, postSizes, sumWeight - preSideSumWeight);
		}
		return flats;
	}

	const flats = $derived(
		bsp(childVals || [], [xOffset, yOffset], [width, height], sumW, 0, [], pad)
	);
</script>

{#if childVals.length == 0}
	<rect
		x={xOffset}
		y={yOffset}
		{width}
		{height}
		style="--crgb: {getColorArr((colorStart + colorEnd) / 2)}; --transition-ms: {transitionMs}ms"
	/>
{:else}
	{#each flats as node, i (i)}
		<TileTreeMap
			data={node.data}
			width={theOne(node, node.sizes[0], width, 1)}
			height={theOne(node, node.sizes[1], height, 1)}
			xOffset={theOne(node, node.offsets[0], xOffset, node.offsets[0] + node.sizes[0] / 2)}
			yOffset={theOne(node, node.offsets[1], yOffset, node.offsets[1] + node.sizes[1] / 2)}
			open={openChildren.includes(node.name)}
			colorStart={open ? colorStart + colorStep * i : colorStart}
			showText={open}
			colorEnd={open ? colorStart + colorStep * (i + 1) : colorEnd}
			{transitionMs}
			maxPad={theOne(node, maxPad * (node.sizes[0] / width), maxPad, 0)}
		/>
	{/each}
{/if}

{#if !open && showText}
	<BrokenFittedText
		text={data.name}
		width={width * (1 - 2 * edgePad)}
		height={height * (1 - 2 * edgePad)}
		fadeMs={transitionMs}
		transMs={transitionMs}
		x={xOffset + width * edgePad}
		y={yOffset + height - height * edgePad}
	/>
{/if}

<style>
	rect {
		fill: rgba(var(--crgb), 0.6);
		transition: all var(--transition-ms);
	}
</style>
