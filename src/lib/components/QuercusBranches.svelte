<script lang="ts">
	import { linkVertical } from 'd3-shape';
	import { fade } from 'svelte/transition';
	import type {
		EmbeddedNode,
		TreeInfo,
		OffsetInfo,
		LevelVisual,
		AttributeLabels,
		QcSpec,
		BareNode
	} from '$lib/tree-types';
	import { getNodeByPath } from '$lib/tree-functions';
	import BrokenFittedText from './BrokenFittedText.svelte';
	import { getColor } from '$lib/style-util';
	import { getDispatch, treeInteract } from '$lib/tree-events';

	export let qcSpec: QcSpec;
	export let attributeLabels: AttributeLabels;
	export let visibleTreeInfo: TreeInfo;
	export let selectionState: BareNode;
	export let levelVisuals: LevelVisual = [];
	export let pathInCompleteTree: string[] = [];

	//export let treeVizKind: TreeVizKind = 'verticalRectangle';

	export let branchReachBack = 0;
	export let rootWidth = 30;
	export let treeWidth = 70;
	export let childRate = 0.2;
	export let overHangRate = 0.05;
	export let preStraightRate = 0.05;
	export let treeXOffset = 0;

	export let childBaseSize = 2.9;

	export let linkSurfaceRate = 0.8;
	export let childrenInternalMargin = 0.9;

	export let parentSideMargin = 0.8;
	//export let childSideMargin = 3.8; TODO

	//only internally passed

	export let width = rootWidth;
	export let xOffset = (treeWidth - rootWidth) / 2 + treeXOffset;

	const dispatch = getDispatch();

	const rectangleLinkPath = linkVertical()
		// @ts-ignore
		.source((d) => d.start)
		// @ts-ignore
		.target((d) => d.end);

	const defO = (n: number | undefined) => (n === undefined ? 0 : n);

	$: onLevel = pathInCompleteTree.length;
	$: childLevel = onLevel + 1;

	$: visibleNode = getNodeByPath(pathInCompleteTree, visibleTreeInfo.tree);
	$: nChildren = Object.keys(visibleNode?.children || {}).length;

	$: currentLevelViz = levelVisuals[onLevel];
	$: nSiblings = visibleTreeInfo.meta[onLevel].totalNodes;
	$: nChildLevelNodes = visibleTreeInfo.meta[childLevel]?.totalNodes || 0;

	$: [yOffset, childSize, topExtend, overHangSize] = [
		currentLevelViz?.topOffset,
		...[childRate, preStraightRate, overHangRate].map((x) => currentLevelViz?.totalSize * x)
	].map(defO);
	$: branchYEnd = yOffset + defO(currentLevelViz?.totalSize * (1 - childRate - preStraightRate));
	$: childrenYOffset = branchYEnd + childSize;
	$: pYStart = yOffset + topExtend;

	$: centralLinkSourceWidth = width - 2 * parentSideMargin;
	$: linkInternalMargin =
		(centralLinkSourceWidth * (1 - linkSurfaceRate)) / (nChildren > 1 ? nChildren - 1 : 1);

	$: minimumLinkSurface = (centralLinkSourceWidth * linkSurfaceRate) / (nChildren * 1.8);

	$: divisibleChildSpace =
		treeWidth - childBaseSize * nChildLevelNodes - childrenInternalMargin * (nChildLevelNodes - 1);

	function parseChild(childId: string, childNode: EmbeddedNode) {
		const cachedProps = {
			pathInCompleteTree: [...pathInCompleteTree, childId],
			...getLeftOffsetAndWidth(
				treeXOffset,
				childNode.weight,
				childNode?.totalOffsetOnLevel,
				childBaseSize,
				divisibleChildSpace,
				visibleTreeInfo.meta[childLevel]?.totalWeight || 1,
				childrenInternalMargin
			)
		};

		const linkSourceSetup = getLeftOffsetAndWidth(
			xOffset + parentSideMargin,
			childNode.weight,
			childNode?.totalOffsetAmongSiblings,
			minimumLinkSurface,
			centralLinkSourceWidth * (nChildren > 1 ? linkSurfaceRate : 1) -
				minimumLinkSurface * nChildren,
			visibleNode?.childrenSumWeight || 1,
			linkInternalMargin
		);

		const lSize = {
			parent: linkSourceSetup.width,
			child: cachedProps.width
		};

		const pDown = {
			start: [linkSourceSetup.xOffset, pYStart],
			end: [cachedProps.xOffset, branchYEnd]
		};
		const pUp = {
			start: [pDown.end[0] + lSize.child, branchYEnd],
			end: [pDown.start[0] + lSize.parent, pYStart]
		};

		const ySize = childSize + (childNode.isSelected ? overHangSize : 0);
		// @ts-ignore
		const downWardP = `${rectangleLinkPath(pDown)} v ${ySize} h ${lSize.child}`;
		// @ts-ignore
		const upWardP = `v ${-ySize} ${rectangleLinkPath(pUp)} v ${
			-topExtend - branchReachBack
		} h ${-lSize.parent}`;
		const linkPath = downWardP + upWardP + ` v ${topExtend + branchReachBack}`;

		return {
			id: childId,
			cachedProps,
			vizInfo: {
				linkPath,
				width: lSize.child,
				colorStr: getColor(childNode.scaleEnds.mid),
				strId: cachedProps.pathInCompleteTree.join('-')
			},
			childNode
		};
	}

	function getLeftOffsetAndWidth(
		baseOffset: number,
		weight: number,
		totalOffset: OffsetInfo | undefined,
		baseSize: number,
		divisibleSpace: number,
		totalWeight: number,
		internalMargin: number
	) {
		const fDiv = (x: number | undefined) => (divisibleSpace * (x || 0)) / totalWeight;
		const width = baseSize + fDiv(weight);
		const xOffset =
			baseOffset +
			(totalOffset?.rank || 0) * (baseSize + internalMargin) +
			fDiv(totalOffset?.weight);
		return { width, xOffset };
	}

	function getParsedChildren(visibleNode: EmbeddedNode | undefined, _: object) {
		return Object.entries(visibleNode?.children || {}).map(([id, child]) => parseChild(id, child));
	}

	$: parsedChildren = getParsedChildren(visibleNode, currentLevelViz);
</script>

{#each parsedChildren as { id, cachedProps, vizInfo, childNode } (id)}
	<defs>
		<linearGradient id="path-grad-{vizInfo.strId}" gradientTransform="rotate(90)">
			<stop
				offset="0%"
				stop-opacity={childNode.isSelected ? '80%' : '5%'}
				stop-color={vizInfo.colorStr}
			/>
			<stop
				offset="20%"
				stop-opacity={childNode.isSelected ? '80%' : '15%'}
				stop-color={vizInfo.colorStr}
			/>
			<stop
				offset="50%"
				stop-opacity={childNode.isSelected ? '80%' : '25%'}
				stop-color={vizInfo.colorStr}
			/>
		</linearGradient>
	</defs>

	<path
		transition:fade={{ duration: 300 }}
		d={vizInfo.linkPath}
		fill="url('#path-grad-{vizInfo.strId}')"
	/>
	<rect
		fill-opacity={0.25 + Math.abs(childNode.specMetric.normalizedMetric) / 1.5}
		x={cachedProps.xOffset}
		y={branchYEnd +
			childSize / 2 -
			(childNode.specMetric.normalizedMetric < 0
				? 0
				: (childNode.specMetric.normalizedMetric * childSize) / 2)}
		height={(Math.abs(childNode.specMetric.normalizedMetric) * childSize) / 2}
		width={treeWidth / 20}
	/>

	<g style="--y-off: {childrenYOffset}px; --x-off: {cachedProps.xOffset + vizInfo.width * 0.1}px">
		<BrokenFittedText text={childNode.name} width={vizInfo.width * 0.8} height={childSize} />
	</g>

	<!-- svelte-ignore a11y-mouse-events-have-key-events -->
	<!-- svelte-ignore a11y-click-events-have-key-events -->
	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<rect
		x={cachedProps.xOffset}
		y={branchYEnd}
		fill-opacity="0"
		height={childSize}
		width={vizInfo.width}
		on:mouseover={treeInteract(
			dispatch,
			'highlight',
			cachedProps.pathInCompleteTree,
			cachedProps.xOffset + cachedProps.width / 2,
			branchYEnd
		)}
		on:mouseleave={treeInteract(dispatch, 'de-highlight', cachedProps.pathInCompleteTree, 0, 0)}
		on:click={treeInteract(dispatch, 'toggle-select', cachedProps.pathInCompleteTree, 0, 0)}
	/>

	{#if childNode.children}
		<svelte:self
			{...cachedProps}
			{qcSpec}
			{attributeLabels}
			{visibleTreeInfo}
			{selectionState}
			{levelVisuals}
			{treeWidth}
			{treeXOffset}
			{childRate}
			{overHangRate}
			{preStraightRate}
			{childBaseSize}
			{linkSurfaceRate}
			{childrenInternalMargin}
			parentSideMargin={0}
			on:ti
		/>
	{/if}
{/each}

<style>
	path,
	rect,
	stop {
		transition: 0.8s;
	}
</style>
