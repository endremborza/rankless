<script lang="ts">
	import type { AttributeLabels, TreeSpec } from '$lib/wire/rankless_trees/io';
	import { MAX_LEVEL_COUNT } from '$lib/constants';
	import { CHAR_W, MONO } from '$lib/utils/cards';
	import type * as tt from '$lib/tree-types';
	import * as tf from '$lib/tree-functions';
	import BrokenFittedText from './BrokenFittedText.svelte';
	import QuercusBranches from './QuercusBranches.svelte';

	type RectShape = { x: number; y: number; height: number; width: number };
	let rootD2 = 25;
	let headerRate = 0.11;
	let overHangRate = 0.05;
	let minimumChildWidth = 2.5;
	let fbRatio = 1200 / 630; // 227 linkedin

	export let treeSpec: TreeSpec;
	export let tree: tt.ResponseNode;
	export let attributeLabels: AttributeLabels;

	export let selectionState: tt.BareNode = { children: {} };
	export let controlSpecs = tf.getDefaultControlSpecs(treeSpec.defaultIsSpec);

	export let childD1Rate = 0.3;
	export let height = 100;
	export let width = height * fbRatio;
	export let x = 0;
	export let y = -height * (headerRate + 0.05);
	export let rootName = '';
	export let d2Offset = (height - rootD2) / 2.5;
	export let headerShape: RectShape = {
		height: height * headerRate,
		width: rootD2,
		x: d2Offset,
		y: -height * headerRate
	};
	export let viewBox = `${x} ${y} ${width} ${height}`;
	export let showText = true;

	// Text is fitted by character count in the monospace face the standalone SVG names.
	export let heightMultiplier: number = 1.5;
	export let widthMultiplier: number = CHAR_W.mono;
	export let minLabelScale = 0;

	let levelOutSpecs: tt.LevelOutSpec[] = tf.getDefaultLevelSpecs();
	let visibleTreeInfo = tf.deriveVisibleTree(
		tree,
		controlSpecs,
		selectionState,
		attributeLabels,
		treeSpec
	);

	function updateLevelSpecs(tree: tt.TreeInfo, svgD1: number) {
		let visibleLevelCount = 1;
		for (let meta of (tree.meta || []).slice(2)) {
			if (meta.totalNodes > 0) visibleLevelCount++;
		}
		let topOffset = 0;
		const stepSize = svgD1 / visibleLevelCount;
		for (let i = 0; i < MAX_LEVEL_COUNT; i++) {
			levelOutSpecs[i].totalSize = stepSize;
			levelOutSpecs[i].topOffset = topOffset;
			levelOutSpecs[i].levelOptions = [];
			levelOutSpecs[i].isVisible = i < visibleLevelCount;
			topOffset += levelOutSpecs[i].totalSize;
			if (i == visibleLevelCount - 1) topOffset += svgD1 / 2;
		}
	}

	$: updateLevelSpecs(visibleTreeInfo, height * 0.75);

	let branchReachBack = (height * headerRate) / 10;
	export let treeD2Offset = 10;
	export let treeD2 = width * 0.8;

	// on:ti={handleInteraction}
</script>

<svg {viewBox} xmlns="http://www.w3.org/2000/svg" font-family={MONO} font-size="10">
	<QuercusBranches
		{branchReachBack}
		{d2Offset}
		{rootD2}
		{visibleTreeInfo}
		{levelOutSpecs}
		{treeD2}
		{treeD2Offset}
		{childD1Rate}
		{overHangRate}
		{heightMultiplier}
		{widthMultiplier}
		{showText}
		{minLabelScale}
		childBaseSize={minimumChildWidth}
	/>
	{#if showText}
		<BrokenFittedText
			height={headerShape.height * 0.7}
			width={headerShape.width * 0.8}
			text={rootName}
			anchor="center"
			bottomAligned={false}
			x={headerShape.x + headerShape.width / 2}
			y={headerShape.y + headerShape.height * 0.75}
			allowRotation={false}
			{heightMultiplier}
			{widthMultiplier}
		/>
	{/if}
</svg>
