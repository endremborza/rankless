<script lang="ts">
	import type {
		AttributeLabels,
		NamedNode,
		PathInTree,
		QcSpec,
		SpecBaseOptions,
		WeightedNode
	} from '$lib/tree-types';
	import { formatNumber } from '$lib/text-format-util';
	import { getNodeByPath, getChildName, getEntityKind } from '$lib/tree-functions';
	import {
		DEFAULT_SPEC_BASES,
		getSpecMetricObject,
		specBaseStrToKind
	} from '$lib/metric-calculation';
	import type { EntityType } from '$lib/constants';

	export let rootId: string;
	export let path: PathInTree;
	export let qcSpec: QcSpec;
	export let attributeLabels: AttributeLabels;
	export let weightedRoot: WeightedNode;
	export let specBaselineOptions: SpecBaseOptions;

	export let levelOfDetail = 0;

	const CONCEPT_DESC_FRAME = 'Where the original paper was categorized as';
	const PUB_DESC_FRAME = 'Cited by paper published';
	const REGION_DESC_FRAME = PUB_DESC_FRAME + ' in';
	const INST_DESC_FRAME = PUB_DESC_FRAME + ' by';

	const DESC_PREFIXES: Record<EntityType, string> = {
		Country: REGION_DESC_FRAME,
		Continent: REGION_DESC_FRAME,
		Institution: INST_DESC_FRAME,
		Concept: CONCEPT_DESC_FRAME,
		SubConcept: CONCEPT_DESC_FRAME
	};

	$: leafEntityKind = getEntityKind(path, qcSpec);

	function getNodes(path: PathInTree, weightedRoot: WeightedNode): NamedNode[] {
		if (qcSpec?.root_entity_type === undefined) {
			return [];
		}
		const nodes = [
			{ ...weightedRoot, name: attributeLabels[qcSpec.root_entity_type][rootId].name }
		];
		for (let i = 0; i < path.length; i++) {
			const parentPath = path.slice(0, i + 1);
			const pNode = getNodeByPath(parentPath, weightedRoot);
			const name = getChildName(parentPath, attributeLabels, qcSpec);
			nodes.push({ ...(pNode || { weight: 0 }), name });
		}
		return nodes;
	}

	function getAllMetrics(
		weightedRoot: WeightedNode,
		path: PathInTree,
		rootId: string,
		qcSpec: QcSpec,
		specBaselineOptions: SpecBaseOptions,
		attributeLabels: AttributeLabels
	) {
		const out = [];
		if (levelOfDetail > 0) {
			for (const specK of Object.keys(specBaselineOptions)) {
				const baseKind = specBaseStrToKind(specK);
				if (baseKind.target == leafEntityKind) {
					out.push({
						baseKind,
						specMetricObj: getSpecMetricObject(
							weightedRoot,
							baseKind,
							path,
							rootId,
							qcSpec,
							specBaselineOptions,
							attributeLabels
						)
					});
				}
			}
		}
		return out;
	}

	function getTrueFilters(qcSpec: QcSpec) {
		const out = [];
		for (let i = 0; i < path.length; i++) {
			let currBif = qcSpec.bifurcations[i];
			let nextBif = qcSpec.bifurcations[i + 1];
			if (i == path.length - 1 || currBif.resolver_id != nextBif.resolver_id) {
				const entityType = currBif.attribute_kind;
				const entityName = getChildName(path.slice(0, i + 1), attributeLabels, qcSpec);
				out.push({ entityType, prefixStr: DESC_PREFIXES[entityType], entityName });
			}
		}
		return out;
	}

	function getVolumeInfo(leaf: WeightedNode, parent: WeightedNode) {
		const num = leaf?.weight || 0;
		const comparison = (parent?.weight || 0) / Object.keys(parent?.children || {}).length;
		const rate = num / comparison;
		return { num, comparison, rate, desc: getDesc(rate) };
	}

	function getDesc(rate: number) {
		let desc = 'Average';
		if (rate > 1.2) {
			desc = 'High';
		} else if (rate < 0.75) {
			desc = 'Low';
		}
		return desc;
	}

	$: pathNodes = getNodes(path || [], weightedRoot);
	$: specMetrics = getAllMetrics(
		weightedRoot,
		path,
		rootId,
		qcSpec,
		specBaselineOptions,
		attributeLabels
	);

	$: parent = pathNodes[pathNodes.length - 2];
	$: leaf = pathNodes[pathNodes.length - 1];

	$: volumeInfo = getVolumeInfo(leaf, parent);
	$: specInfo = getSpecMetricObject(
		weightedRoot,
		DEFAULT_SPEC_BASES[leafEntityKind],
		path,
		rootId,
		qcSpec,
		specBaselineOptions,
		attributeLabels
	);

	$: trueFilters = getTrueFilters(qcSpec);
	$: levelEntityType = qcSpec.bifurcations[path.length - 1]?.attribute_kind;
</script>

{#if path != undefined}
	<div class="box-container">
		<div id="title-row">
			{#if levelOfDetail == 0}
				<h2>{leaf.name}</h2>
			{:else}
				<h2>Papers published by {attributeLabels[qcSpec.root_entity_type][rootId].name}</h2>
				{#each trueFilters as trueFilter}
					<div class="title-elem">
						<h2>{trueFilter.prefixStr} {trueFilter.entityName}</h2>
					</div>
				{/each}
			{/if}
		</div>
		<div class="detail-cols">
			<div id="volume-col">
				<h3>
					{formatNumber(volumeInfo.num)} citation{#if volumeInfo.num > 1}s{/if}
				</h3>
				<p>
					<b>{(volumeInfo.num / volumeInfo.comparison).toFixed(2)}</b> times the average {levelEntityType}
					({formatNumber(volumeInfo.comparison)}) under {parent.name}
				</p>
			</div>
			<div id="spec-col">
				<h3>{getDesc(specInfo.specMetric)} Specialization</h3>
				<p>
					<b>{(specInfo.nodeRate * 100).toFixed(2)}%</b> of total impact
				</p>
				<p>
					{(specInfo.baselineRate * 100).toFixed(2)}% ({formatNumber(
						specInfo.nodeDivisor * specInfo.baselineRate
					)} citations) expected based on {leaf.name} impact rate of all {qcSpec.root_entity_type}s
				</p>
			</div>

			{#if levelOfDetail > 0}
				<div>
					<h3>Specialization Details</h3>
					{#each specMetrics as { baseKind, specMetricObj }}
						<p>
							Based on the impact rate of {#if baseKind.basis == 'Global'}
								all other Institutions
							{:else}
								Institutions in the same {baseKind.basis}
							{/if}
							{#if baseKind.hierarchy != 'Global'}
								when citing papers belong to the same {baseKind.hierarchy}
							{/if} we expect {formatNumber(specMetricObj.nodeDivisor * specMetricObj.baselineRate)}
							citations, the true number is <b>{(specMetricObj.specMetric * 100).toFixed(2)}%</b>
							of this
						</p>
					{/each}
				</div>
			{/if}
		</div>
	</div>
{/if}

<style>
	h2 {
		text-align: center;
	}

	.box-container {
		display: flex;
		flex-direction: column;
		height: 100%;
		justify-content: space-around;
	}

	#title-row {
		width: 100%;
		display: flex;
		justify-content: space-around;
	}

	.title-elem {
		padding-right: 10px;
		padding-left: 10px;
	}

	.detail-cols {
		display: flex;
		justify-content: space-evenly;
	}

	.detail-cols > div {
		padding: 20px;
		text-align: center;
	}

	#volume-col {
		width: 50%;
		border-right: 5px solid black;
	}

	#spec-col {
		width: 50%;
	}
</style>
