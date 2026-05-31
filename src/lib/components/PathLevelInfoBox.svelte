<script lang="ts">
	import type { AttributeLabels, PathInTree, TreeSpec, ResponseNode } from '$lib/tree-types';
	import { nameById, UNKNOWN_NAME } from '$lib/tree-functions';
	import { pluralize, getSpecDesc } from '$lib/text-format-util';
	import { getSpecMetricObject, type SpecInfo } from '$lib/metric-calculation';
	import WorkElem from './WorkElem.svelte';
	import LoadingCircle from './LoadingCircle.svelte';
	import { prefetchPaper } from '$lib/stores';

	export let path: PathInTree;
	export let treeSpec: TreeSpec;
	export let rootId: number;
	export let rootName: string;
	export let attributeLabels: AttributeLabels;
	export let rootNode: ResponseNode;
	export let showPaper: boolean = false;
	export let hasSpaceForPaper: boolean = false;
	export let backupNames: Record<number, string> = {};

	export let armingPath: number[] | null = null;
	export let delay = 1200;

	let instId: number | undefined;
	let citeText = '';

	function getNodes(
		path: PathInTree,
		root: ResponseNode,
		attributeLabels: AttributeLabels,
		treeSpec: TreeSpec
	): {
		name: string;
		linkCount: number;
		sourceCount: number;
		topSourceId: number;
		topSourceLinks: number;
		spec: SpecInfo;
	}[] {
		instId = undefined;
		const citeRestricts = [];
		if (treeSpec?.rootType === undefined) {
			return [];
		}
		if (treeSpec.rootType == 'institutions') {
			instId = rootId;
		}
		const nodes = [
			{
				linkCount: root.linkCount,
				sourceCount: root.sourceCount,
				topSourceId: root.topSourceId,
				topSourceLinks: root.topSourceLinks,
				name: rootName,
				spec: { nodeRate: 0, specMetric: 0, baselineRate: 0 }
			}
		];
		let divisors = [];
		let currentNode = rootNode;
		for (let i = 0; i < path.length; i++) {
			divisors.push(currentNode.linkCount);
			const childId = path[i];
			const bd = treeSpec.breakdowns[i];
			const entityKind = bd.attributeType;
			if (instId == undefined && entityKind == 'institutions') {
				instId = childId;
			}
			if (currentNode.children == undefined) {
				break;
			}
			let name = nameById(attributeLabels, entityKind, childId);
			if (name == UNKNOWN_NAME) {
				let backupName = backupNames[childId];
				if (backupName != undefined) name = backupName;
			}
			if (!bd.sourceSide) {
				citeRestricts.push(name);
			}
			currentNode = currentNode.children[childId] || { linkCount: 0, children: {} };
			nodes.push({
				name,
				linkCount: currentNode.linkCount,
				sourceCount: currentNode.sourceCount,
				topSourceId: currentNode.topSourceId,
				topSourceLinks: currentNode.topSourceLinks,
				spec: getSpecMetricObject(
					currentNode,
					divisors[bd.specDenomInd],
					attributeLabels[entityKind],
					childId
				)
			});
		}
		let leaf = nodes[nodes.length - 1];
		if (citeRestricts.length > 0) {
			citeText =
				pluralize('citation', leaf.topSourceLinks || 0) +
				' on branch of ' +
				citeRestricts.join(' > ');
		} else {
			citeText = pluralize('citation', leaf.topSourceLinks || 0);
		}
		return nodes;
	}

	function scheduleAutoShow(hasSpace: boolean, leaf: { sourceCount: number; topSourceId: number }) {
		if (!hasSpace || (leaf?.sourceCount || 0) === 0) return;
		showPaper = true;
	}

	function preloadArmedPaper(path: PathInTree | null) {
		if (!path) return;
		let node = rootNode;
		for (const childId of path) {
			if (!node?.children) return;
			node = node.children[childId];
		}
		if (node?.topSourceId) prefetchPaper(node.topSourceId);
	}

	$: pathNodes = getNodes(path || [], rootNode, attributeLabels, treeSpec);
	$: leaf = pathNodes[pathNodes.length - 1];
	$: scheduleAutoShow(hasSpaceForPaper, leaf);
	$: preloadArmedPaper(armingPath);
	$: if (leaf?.topSourceId) prefetchPaper(leaf.topSourceId);
	$: expanded = showPaper && (leaf.sourceCount || 0) > 0;
	$: citePrefix =
		path.length > 0 && (leaf.linkCount || 0) > 0
			? `(${(leaf.spec.nodeRate * 100).toFixed(2)}%) `
			: '';
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_mouse_events_have_key_events -->
<div class="plibox-container shadowy" role="none" tabindex="-1">
	<span class="load-indicator">
		<LoadingCircle isArming={armingPath != null} {delay} />
	</span>
	{#if path != undefined && leaf != undefined}
		<div class="pli-basics-container padded">
			<h2 class="vw-lg">{leaf.name}</h2>
			<p class="vw-base">
				{#if path.length > 0 && (leaf.linkCount || 0) > 0}
					{getSpecDesc(leaf.spec.specMetric)} Specialization
				{/if}
			</p>
			<p class="vw-base">
				{pluralize('paper', leaf.sourceCount || 0)}
				receiving
				{pluralize(`${citePrefix}citation`, leaf.linkCount || 0)}
			</p>
		</div>
		<div class="paper-container">
			{#if expanded}
				<WorkElem workId={leaf.topSourceId} {citeText} {attributeLabels} {instId} />
			{:else if (leaf.sourceCount || 0) > 0 && !hasSpaceForPaper}
				<button class="show-paper-btn" on:click={() => (showPaper = true)}>Show top paper</button>
			{/if}
		</div>
	{/if}
</div>

<style>
	p {
		text-align: center;
		margin: 0px;
	}

	h2 {
		margin-bottom: calc(var(--unified-padding) / 2);
		word-break: break-word;
		overflow-wrap: break-word;
		text-align: center;
	}

	.plibox-container {
		position: relative;
		width: 100%;
		height: 100%;
		display: flex;
		justify-content: start;
		flex-direction: column;
		gap: calc(var(--unified-padding) / 2);
		overflow: hidden;
		min-width: 0;
	}

	.pli-basics-container {
		display: flex;
		gap: calc(var(--unified-padding) / 2);
		flex-direction: column;
		align-items: center;
		width: 100%;
	}

	.paper-container {
		flex: 1;
		min-height: 0;
		overflow: hidden;
	}

	.load-indicator {
		position: absolute;
		top: var(--unified-padding);
		right: var(--unified-padding);
	}

	.show-paper-btn {
		display: block;
		width: fit-content;
		margin: var(--unified-padding) auto 0;
		background: none;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		border-radius: var(--control-bar-pill-radius);
		padding: var(--control-bar-pill-pad);
		font-family: inherit;
		font-size: var(--control-bar-font);
		cursor: pointer;
		color: inherit;
		opacity: 0.6;
		transition: opacity 0.15s;
	}

	.show-paper-btn:hover {
		opacity: 1;
	}

	@media (min-width: 900px) {
		.show-paper-btn {
			display: none;
		}
	}
</style>
