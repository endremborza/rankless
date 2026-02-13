<script lang="ts">
	import { fade } from 'svelte/transition';
	import type { EmbeddedNode, TreeInfo, OffsetInfo, LevelOutSpec } from '$lib/tree-types';
	import { getNodeByPath } from '$lib/tree-functions';
	import BrokenFittedText from './BrokenFittedText.svelte';
	import { getColor } from '$lib/style-util';
	import { treeInteract, type EventMap } from '$lib/tree-events';
	import { getSankeyPath } from '$lib/visual-util';
	import { createEventDispatcher } from 'svelte';
	import { HIGH_OP, LOW_OP } from '$lib/constants';

	export let visibleTreeInfo: TreeInfo;
	export let levelOutSpecs: LevelOutSpec[] = [];
	export let pathInCompleteTree: number[] = [];

	//export let treeVizKind: TreeVizKind = 'verticalRectangle';

	export let branchReachBack = 0;
	export let rootD2 = 30;
	export let treeD2 = 70;
	export let childD1Rate = 0.2;
	export let overHangRate = 0.05;
	export let preStraightRate = 0.05;
	export let treeD2Offset = 0;

	export let childBaseSize = 2.9;
	export let linkSurfaceRate = 0.8;
	export let childrenInternalMargin = 0.9;

	export let parentSideMargin = 0.8;
	//export let childSideMargin = 3.8; TODO

	export let showText = true;
	export let heightMultiplier: number = 1.2;
	export let widthMultiplier: number = 0.6;

	export let hoverDelay: number = 800;

	//only internally passed
	export let d2Offset = (treeD2 - rootD2) / 2 + treeD2Offset;

	const dispatch = createEventDispatcher<EventMap>();
	const defO = (n: number | undefined) => (n === undefined ? 0 : n);

	$: onLevel = pathInCompleteTree.length;
	$: childLevel = onLevel + 1;

	$: visibleNode = getNodeByPath(pathInCompleteTree, visibleTreeInfo.tree);
	$: nChildren = Object.keys(visibleNode?.children || {}).length;

	$: currentLevelViz = levelOutSpecs[onLevel];
	$: nChildLevelNodes = visibleTreeInfo.meta[childLevel]?.totalNodes || 0;

	$: d1Offset = defO(currentLevelViz?.topOffset);
	$: [pathLength, childD1, preStraightSize, overHangSize] = [
		1 - childD1Rate - preStraightRate - overHangRate,
		childD1Rate,
		preStraightRate,
		overHangRate
	].map((x) => defO(currentLevelViz?.totalSize * x));
	$: pD1Start = d1Offset + preStraightSize;
	$: branchD1End = pD1Start + pathLength;
	$: childrenD1Offset = branchD1End + childD1;
	$: downWardStart = branchReachBack + preStraightSize;

	$: centralLinkSourceWidth = rootD2 - 2 * parentSideMargin;
	$: linkInternalMargin =
		(centralLinkSourceWidth * (1 - linkSurfaceRate)) / (nChildren > 1 ? nChildren - 1 : 1);

	$: minimumLinkSurface = (centralLinkSourceWidth * linkSurfaceRate) / (nChildren * 1.8);

	$: divisibleChildSpace =
		treeD2 - childBaseSize * nChildLevelNodes - childrenInternalMargin * (nChildLevelNodes - 1);

	let timeout: ReturnType<typeof setTimeout>;

	function handleEnter(path: number[], x: number, y: number) {
		return () => {
			treeInteract(dispatch, 'arm', path, x, y)();
			timeout = setTimeout(() => {
				treeInteract(dispatch, 'highlight', path, x, y)();
				treeInteract(dispatch, 'disarm', [], 0, 0)();
			}, hoverDelay);
		};
	}

	function handleLeave() {
		clearTimeout(timeout);
		treeInteract(dispatch, 'disarm', [], 0, 0)();
	}

	function parseChild(childId: number, childNode: EmbeddedNode) {
		const cachedProps = {
			pathInCompleteTree: [...pathInCompleteTree, childId],
			...getLeftOffsetAndWidth(
				treeD2Offset,
				childNode.weight,
				childNode?.totalOffsetOnLevel,
				childBaseSize,
				divisibleChildSpace,
				visibleTreeInfo.meta[childLevel]?.totalWeight || 1,
				childrenInternalMargin
			)
		};

		const linkSourceSetup = getLeftOffsetAndWidth(
			d2Offset + parentSideMargin,
			childNode.weight,
			childNode?.totalOffsetAmongSiblings,
			minimumLinkSurface,
			centralLinkSourceWidth * (nChildren > 1 ? linkSurfaceRate : 1) -
				minimumLinkSurface * nChildren,
			visibleNode?.childrenSumWeight || 1,
			linkInternalMargin
		);

		const lSize = {
			parent: linkSourceSetup.rootD2,
			child: cachedProps.rootD2
		};

		const d1Size = childD1 + (childNode.isSelected ? overHangSize : 0);
		const cTop = {
			x: linkSourceSetup.d2Offset,
			y: pD1Start
		};
		const cBot = {
			x: cachedProps.d2Offset,
			y: branchD1End
		};

		let linkPath = getSankeyPath(cTop, cBot, lSize, d1Size, downWardStart);
		let textShape = {
			x: cachedProps.d2Offset + lSize.child * 0.18,
			y: childrenD1Offset - childD1 * 0.05,
			height: childD1 * 0.9,
			width: lSize.child * 0.64
		};
		const hoverShape = {
			x: cachedProps.d2Offset,
			y: branchD1End,
			height: childD1,
			width: lSize.child
		};
		return {
			id: childId,
			cachedProps,
			vizInfo: {
				linkPath,
				d2Size: lSize.child,
				colorStr: getColor(childNode.scaleEnds.mid),
				strId: cachedProps.pathInCompleteTree.join('-')
			},
			childNode,
			textShape,
			hoverShape
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
		const rootD2 = baseSize + fDiv(weight);
		const d2Offset =
			baseOffset +
			(totalOffset?.rank || 0) * (baseSize + internalMargin) +
			fDiv(totalOffset?.weight);
		return { rootD2, d2Offset };
	}

	function getParsedChildren(visibleNode: EmbeddedNode | undefined, _: object) {
		return Object.entries(visibleNode?.children || {}).map(([id, child]) =>
			parseChild(parseInt(id), child)
		);
	}

	$: parsedChildren = getParsedChildren(visibleNode, currentLevelViz);
</script>

{#each parsedChildren as { id, cachedProps, vizInfo, childNode, textShape, hoverShape } (id)}
	<defs>
		<linearGradient id="path-grad-{vizInfo.strId}" gradientTransform="rotate(90)">
			{#each [[0, 5], [20, 15], [50, LOW_OP]] as [offsetPct, opaPct]}
				<stop
					offset="{offsetPct}%"
					stop-opacity="{childNode.isSelected ? HIGH_OP : opaPct}%"
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

	{#if showText}
		<BrokenFittedText text={childNode.name} {...textShape} {heightMultiplier} {widthMultiplier} />
	{/if}

	<!-- svelte-ignore a11y-mouse-events-have-key-events -->
	<!-- svelte-ignore a11y-click-events-have-key-events -->
	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<rect
		{...hoverShape}
		fill-opacity="0"
		on:mouseover={handleEnter(cachedProps.pathInCompleteTree, hoverShape.x, hoverShape.y)}
		on:mouseleave={handleLeave}
		on:click={treeInteract(dispatch, 'toggle-select', cachedProps.pathInCompleteTree, 0, 0)}
	/>

	{#if childNode.children}
		<svelte:self
			{...cachedProps}
			{visibleTreeInfo}
			{levelOutSpecs}
			{treeD2}
			{treeD2Offset}
			{childD1Rate}
			{overHangRate}
			{preStraightRate}
			{childBaseSize}
			{linkSurfaceRate}
			{childrenInternalMargin}
			{heightMultiplier}
			{widthMultiplier}
			{showText}
			{hoverDelay}
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
