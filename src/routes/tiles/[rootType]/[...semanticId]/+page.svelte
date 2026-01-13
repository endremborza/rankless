<script lang="ts">
	import TileTreeMap from '$lib/components/TileTreeMap.svelte';
	import { subfields, fields, domains } from '$lib/assets/data/field-hierarchy.json';
	import { onMount } from 'svelte';
	import type * as tt from '$lib/tree-types';
	import * as tf from '$lib/tree-functions';
	import { BE_REMOTE_URL } from '$lib/constants';

	export let data: {
		view: tt.View;
		conf: tt.FullTreeConfig;
		treeSpecs: tt.TreeSpecs;
	};

	let l1Type: tt.EntityType = 'subfields';
	let tree: tt.NamedNode | undefined;
	let innerWidth: number;
	let innerHeight: number;

	let vbWidth = 3000;
	$: vbHeight = (innerHeight / innerWidth) * vbWidth;

	function getHier(sfi: string): [number, number, number] {
		let sfin = parseInt(sfi);
		let fieldId = subfields[sfin][1] as number;
		let domainId = fields[fieldId][1] as number;
		return [sfin, fieldId, domainId];
	}

	function treeToNamed(node: tt.ResponseNode, atts: tt.AttributeLabels): tt.NamedNode {
		const children: Record<string, tt.NamedNode> = {};
		for (const [attId, child] of Object.entries(node.children || {})) {
			let [sfId, fieldId, domainId] = getHier(attId);
			const att = atts[l1Type][attId];
			if (att === undefined) continue;
			let node = { weight: child.linkCount, name: att.name };
			let parentId = domainId;
			if (children[parentId] == undefined) {
				children[parentId] = { name: domains[domainId], weight: 0, children: {} };
			}
			children[parentId].children[sfId] = node;
			children[parentId].weight += node.weight;
		}
		return {
			name: data.view.name,
			weight: node.linkCount,
			children
		};
	}

	onMount(() => {
		const indsByEntityType = tf.getTreeIndsByEntityType(data.treeSpecs.specs[data.conf.rootType]);
		let treeId = indsByEntityType[l1Type].includes(9) ? 9 : indsByEntityType[l1Type][0];

		const specs = data.treeSpecs.specs[data.conf.rootType];
		for (let i = 0; i < specs.length; i++) {
			const spec = specs[i];
			if (
				spec.breakdowns.length > 0 &&
				spec.breakdowns[0].attributeType === l1Type &&
				spec.breakdowns[0].sourceSide
			) {
				treeId = i;
				break;
			}
		}

		const conf = { ...data.conf, wide: true, treeId };
		fetch(tf.treeBeUrl(BE_REMOTE_URL, conf, 0))
			.then((res) => res.json())
			.then((resp: tt.TreeResponse) => {
				if (resp.tree === undefined) return;
				tree = treeToNamed(resp.tree, resp.atts);
				console.log(tree);
			});
	});
</script>

<svelte:head>
	<title>Tiles | {data.view.name}</title>
</svelte:head>

<h1>{data.view.name}</h1>

<div bind:clientWidth={innerWidth} bind:clientHeight={innerHeight}>
	{#if tree}
		<svg viewBox="0 0 {vbWidth} {vbHeight}">
			<TileTreeMap
				data={tree}
				width={vbWidth}
				height={vbHeight}
				open={true}
				showText={true}
				openChildren={domains}
				expandedChild={domains[1]}
			/>
		</svg>
	{/if}
</div>

<style>
	h1 {
		padding-top: 20px;
		width: 100%;
		text-align: center;
	}
	div {
		height: 80svh;
	}
	svg {
		padding: 2%;
		width: 100%;
		height: 100%;
	}
</style>
