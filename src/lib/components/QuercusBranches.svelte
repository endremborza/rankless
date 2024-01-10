<script lang="ts">
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
	import { rectangleLinkPath } from '$lib/visual-util';

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
	export let childHeightRate = 0.2;
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
	$: [pathLength, childHeight, preStraightSize, overHangSize] = [
		1 - childHeightRate - preStraightRate - overHangRate,
		childHeightRate,
		preStraightRate,
		overHangRate
	].map((x) => defO(currentLevelViz?.totalSize * x));
	$: pYStart = yOffset + preStraightSize;
	$: branchYEnd = pYStart + pathLength;
	$: childrenYOffset = branchYEnd + childHeight;
	$: downWardStart = branchReachBack + preStraightSize;

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

		const pDown = {
			start: [linkSourceSetup.xOffset, pYStart],
			end: [cachedProps.xOffset, branchYEnd]
		};
		const pUp = {
			start: [pDown.end[0] + lSize.child, branchYEnd],
			end: [pDown.start[0] + lSize.parent, pYStart]
		};

		const ySize = childHeight + (childNode.isSelected ? overHangSize : 0);

		// deleting before C removes the M part of path, so it is closed later
		// that is the split(C) magic

		// @ts-ignore
		const downWardP = `${rectangleLinkPath(pDown)} v ${ySize}`;
		// @ts-ignore
		const upWardP = `v ${-ySize} C${rectangleLinkPath(pUp).split('C').pop()} v ${-downWardStart}`;
		const linkPath = `${downWardP} h ${lSize.child} ${upWardP} h ${-lSize.parent}z`;

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
			{#each [[0, 5], [20, 15], [50, 25]] as [offsetPct, opaPct]}
				<stop
					offset="{offsetPct}%"
					stop-opacity={childNode.isSelected ? '80%' : `${opaPct}%`}
					stop-color={vizInfo.colorStr}
				/>
			{/each}
		</linearGradient>
	</defs>

	<path
		transition:fade={{ duration: 300 }}
		d={vizInfo.linkPath}
		fill="url('#path-grad-{vizInfo.strId}')"
	/>

	<BrokenFittedText
		text={childNode.name}
		width={vizInfo.width * 0.64}
		height={childHeight * 0.9}
		y={childrenYOffset - childHeight * 0.05}
		x={cachedProps.xOffset + vizInfo.width * 0.18}
	/>

	<!-- svelte-ignore a11y-mouse-events-have-key-events -->
	<!-- svelte-ignore a11y-click-events-have-key-events -->
	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<rect
		x={cachedProps.xOffset}
		y={branchYEnd}
		fill-opacity="0"
		height={childHeight}
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
			{childHeightRate}
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
	path,
	rect,
	stop {
		transition: 0.8s;
	}
</style>
