<script lang="ts">
	import type { AttributeLabels, PathInTree, TreeSpec, ResponseNode } from '$lib/tree-types';
	import { nameById, UNKNOWN_NAME } from '$lib/tree-functions';
	import { formatNumber, pluralize, getSpecDesc } from '$lib/text-format-util';
	import { getSpecMetricObject, type SpecInfo } from '$lib/metric-calculation';
	import WorkElem from './WorkElem.svelte';

	export let path: PathInTree;
	export let treeSpec: TreeSpec;
	export let rootId: number;
	export let initHeight: number;
	export let rootName: string;
	export let attributeLabels: AttributeLabels;
	export let rootNode: ResponseNode;
	export let showPaper: boolean = false;
	export let backupNames: Record<number, string> = {};

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

	$: pathNodes = getNodes(path || [], rootNode, attributeLabels, treeSpec);
	$: leaf = pathNodes[pathNodes.length - 1];
	$: expanded = showPaper && (leaf.sourceCount || 0) > 0;
	$: citePrefix =
		path.length > 0 && (leaf.linkCount || 0) > 0
			? `(${(leaf.spec.nodeRate * 100).toFixed(2)}%) `
			: '';
</script>

<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-mouse-events-have-key-events -->
<div
	class="hoverover shadowy clickable growing"
	id="plibox-container"
	role="none"
	tabindex="-1"
	style="height: {initHeight * (expanded ? 4 : 1)}px"
	on:click={() => {
		showPaper = !showPaper;
	}}
>
	{#if path != undefined && leaf != undefined}
		<div id="box-container" style="height: {initHeight}px;">
			<h2 class="hover-xl">{leaf.name}</h2>
			<p class="hover-l">
				{#if path.length > 0 && (leaf.linkCount || 0) > 0}
					{getSpecDesc(leaf.spec.specMetric)} Specialization
				{/if}
			</p>
			<p class="hover-l">
				{pluralize('paper', leaf.sourceCount || 0)}
				receiving
				{pluralize(`${citePrefix}citation`, leaf.linkCount || 0)}
			</p>
		</div>
		<div class="growing" style="height: {initHeight * (expanded ? 3 : 0)}px;">
			{#if expanded}
				<WorkElem workId={leaf.topSourceId} {citeText} {attributeLabels} {instId} />
			{/if}
		</div>
	{/if}
</div>

<style>
	p {
		text-align: center;
		font-weight: 600;
	}

	.growing {
		transition: height 350ms ease-in-out;
	}

	#plibox-container {
		width: 100%;
		bottom: 0px;
	}

	#box-container {
		display: flex;
		gap: var(--unified-padding);
		flex-direction: row;
		justify-content: space-between;
		align-items: center;
		padding-left: var(--unified-padding);
		padding-right: var(--unified-padding);
	}
</style>
