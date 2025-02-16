<script lang="ts">
	import type { AttributeLabels, PathInTree, TreeSpec, ResponseNode } from '$lib/tree-types';
	import { nameById } from '$lib/tree-functions';
	import { formatNumber } from '$lib/text-format-util';
	import { getSpecMetricObject, type SpecInfo } from '$lib/metric-calculation';
	import WorkElem from './WorkElem.svelte';

	export let path: PathInTree;
	export let treeSpec: TreeSpec;
	export let rootId: number;
	export let rootName: string;
	export let attributeLabels: AttributeLabels;
	export let rootNode: ResponseNode;
	export let showPaper: boolean = false;

	let instId: number | undefined;

	function getNodes(
		path: PathInTree,
		root: ResponseNode
	): {
		name: string;
		linkCount: number;
		sourceCount: number;
		topSourceId: number;
		topSourceLinks: number;
		spec: SpecInfo;
	}[] {
		instId = undefined;
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
			currentNode = currentNode.children[childId] || { linkCount: 0, children: {} };
			nodes.push({
				name: nameById(attributeLabels, entityKind, childId),
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
		return nodes;
	}

	function getDesc(rate: number) {
		let desc = 'Average';
		if (rate > 2.5) {
			desc = 'Very High';
		} else if (rate > 1.2) {
			desc = 'High';
		} else if (rate < 0.75) {
			desc = 'Low';
		}
		return desc;
	}

	let hoverSpec = false;
	let topRate = 75;

	$: pathNodes = getNodes(path || [], rootNode);
	$: leaf = pathNodes[pathNodes.length - 1];
</script>

{#if path != undefined}
	<div class="top-container" style="height: {showPaper ? topRate : 0}%;">
		{#if showPaper}
			<WorkElem
				workId={leaf.topSourceId}
				workCitations={leaf.topSourceLinks}
				{attributeLabels}
				{instId}
			/>
		{/if}
	</div>
	<div class="box-container" style="height: {showPaper ? 100 - topRate : 100}%;">
		<h2 class="hover-l">{leaf.name}</h2>
		<!-- svelte-ignore a11y-mouse-events-have-key-events -->
		<p
			on:mouseover={() => {
				hoverSpec = false;
			}}
			on:mouseleave={() => {
				hoverSpec = false;
			}}
			class="hover-m"
		>
			{getDesc(leaf.spec.specMetric)} Specialization
		</p>
		{#if hoverSpec}
			<span id="spec-hover">
				metric = {formatNumber(leaf.spec.specMetric, 3)}; base = {leaf.spec.baselineRate}; nodeRate
				= {leaf.spec.nodeRate}; childN={leaf.linkCount}
			</span>
		{/if}
		<p class="hover-m">
			{formatNumber(leaf.linkCount || 0, 0)} ({(leaf.spec.nodeRate * 100).toFixed(2)}%) citation{#if leaf.linkCount > 1}s{/if},
			{formatNumber(leaf.sourceCount || 0, 0)} paper{#if leaf.sourceCount > 1}s{/if}
		</p>
	</div>
{/if}

<style>
	h2 {
		text-align: center;
		padding: 15px;
		margin: 0px;
		text-align: center;
	}

	p {
		text-align: center;
		padding-left: 20px;
	}

	.box-container {
		display: flex;
		flex-direction: row;
		justify-content: space-around;
		align-items: center;
	}

	.top-container {
		display: flex;
		flex-direction: column;
		justify-content: space-around;
		align-items: center;
	}

	#spec-hover {
		position: absolute;
		top: 0px;
		left: 0px;
		padding: 15px;
		background-color: var(--color-theme-darkgrey);
	}
</style>
