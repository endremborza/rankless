<script lang="ts">
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
	import MaskedSankeyPath from './MaskedSankeyPath.svelte';

	export let qcSpec: QcSpec;
	export let attributeLabels: AttributeLabels;
	export let visibleTreeInfo: TreeInfo;
	export let selectionState: BareNode;
	export let levelVisuals: LevelVisual = [];
	export let pathInCompleteTree: string[] = [];

	export let branchReachBack = 0;
	export let rootWidth = 30;
	export let treeWidth = 70;
	export let childRate = 0.2;
	export let overHangRate = 0.05;
	export let preStraightRate = 0.05;
	export let treeXOffset = 0;

	export let childBaseWidth = 2.9;

	export let linkSurfaceRate = 0.8;
	export let childrenInternalMargin = 0.9;

	export let parentSideMargin = 0.8;
	//export let childSideMargin = 3.8; TODO

	//only internally passed
	export let width = rootWidth;
	export let xOffset = (treeWidth - rootWidth) / 2 + treeXOffset;

	const dispatch = getDispatch();

	const defO = (n: number | undefined) => (n === undefined ? 0 : n);

	$: onLevel = pathInCompleteTree.length;
	$: childLevel = onLevel + 1;

	$: visibleNode = getNodeByPath(pathInCompleteTree, visibleTreeInfo.tree);
	$: nChildren = Object.keys(visibleNode?.children || {}).length;

	$: currentLevelViz = levelVisuals[onLevel];
	$: nChildLevelNodes = visibleTreeInfo.meta[childLevel]?.totalNodes || 0;

	$: yOffset = defO(currentLevelViz?.topOffset);
	$: [pathLength, childSize, topExtend, overHangSize] = [
		1 - childRate - preStraightRate - overHangRate,
		childRate,
		preStraightRate,
		overHangRate
	].map((x) => defO(currentLevelViz?.totalSize * x));
	$: branchYEnd = yOffset + topExtend + pathLength;
	$: childrenYOffset = branchYEnd + childSize;

	$: centralLinkSourceWidth = width - 2 * parentSideMargin;
	$: linkInternalMargin =
		(centralLinkSourceWidth * (1 - linkSurfaceRate)) / (nChildren > 1 ? nChildren - 1 : 1);

	$: minimumLinkSurface = (centralLinkSourceWidth * linkSurfaceRate) / (nChildren * 1.8);

	$: divisibleChildSpace =
		treeWidth - childBaseWidth * nChildLevelNodes - childrenInternalMargin * (nChildLevelNodes - 1);

	function parseChild(childId: string, childNode: EmbeddedNode) {
		const cachedProps = {
			pathInCompleteTree: [...pathInCompleteTree, childId],
			...getLeftOffsetAndWidth(
				treeXOffset,
				childNode.weight,
				childNode?.totalOffsetOnLevel,
				childBaseWidth,
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

		const ySize = childSize + (childNode.isSelected ? overHangSize : 0);

		const maskedInfo = {
			widths: lSize,
			heights: { top: branchReachBack + topExtend, path: pathLength, bot: ySize },
			xOffsets: { top: linkSourceSetup.xOffset, bot: cachedProps.xOffset },
			yOffset: yOffset + topExtend
		};
		console.log(maskedInfo);
		return {
			id: childId,
			cachedProps,
			vizInfo: {
				maskedInfo,
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

	<MaskedSankeyPath
		{...vizInfo.maskedInfo}
		cssClass="pass-through"
		id={vizInfo.strId}
		color="url('#path-grad-{vizInfo.strId}')"
	/>

	<g style="--y-off: {childrenYOffset}px; --x-off: {cachedProps.xOffset + vizInfo.width * 0.1}px">
		<BrokenFittedText text={childNode.name} width={vizInfo.width * 0.8} height={childSize} />
	</g>

	<!-- svelte-ignore a11y-mouse-events-have-key-events -->
	<!-- svelte-ignore a11y-click-events-have-key-events -->
	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<rect
		fill-opacity="0"
		height=1
		width=1
		transform="translate({cachedProps.xOffset}, {branchYEnd}) scale({vizInfo.width}, {childSize})"
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
			{childBaseWidth}
			{linkSurfaceRate}
			{childrenInternalMargin}
			parentSideMargin={0}
			on:ti
		/>
	{/if}
{/each}

<style>
	rect,
	stop {
		transition: 0.8s;
	}

	:global(.pass-through) {
		pointer-events: none;
	}
</style>
