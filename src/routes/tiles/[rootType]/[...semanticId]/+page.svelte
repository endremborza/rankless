<script lang="ts">
	import TileTreeMap from '$lib/components/TileTreeMap.svelte';
	import { subfields, fields, domains } from '$lib/assets/data/field-hierarchy.json';
	import { onMount } from 'svelte';
	import type * as tt from '$lib/tree-types';
	import * as tf from '$lib/tree-functions';
	import { BE_REMOTE_URL } from '$lib/constants';
	import { page } from '$app/stores';

	export let data: {
		view: tt.View;
		conf: tt.FullTreeConfig;
		treeSpecs: tt.TreeSpecs;
	};

	let l1Type: tt.EntityType = 'subfields';
	let tree: tt.NamedNode | undefined;
	let innerWidth: number;
	let innerHeight: number;

	let openChildren: string[] = domains.slice(1);
	let expandedChild: string | undefined = undefined;

	let vbWidth = 3000;
	$: vbHeight = (innerHeight / innerWidth) * vbWidth;

	let isPlaying = false;
	let animationStep = 0;
	let currentDomainIndex = 0;
	const animationDomains = domains.filter((d) => d);
	let timeoutId: ReturnType<typeof setTimeout>;

	function animationLoop() {
		if (!animationDomains.length) return;
		const currentDomain = animationDomains[currentDomainIndex];

		switch (animationStep) {
			case 0: // set one open child
				openChildren = [currentDomain];
				expandedChild = undefined;
				break;
			case 1: // expand it
				expandedChild = currentDomain;
				break;
			case 2: // collapse expanded
				expandedChild = undefined;
				break;
			case 3: // clear open children, and move to next domain
				openChildren = [];
				currentDomainIndex = (currentDomainIndex + 1) % animationDomains.length;
				break;
		}

		animationStep = (animationStep + 1) % 4;

		if (isPlaying) {
			timeoutId = setTimeout(animationLoop, 2400);
		}
	}

	function play() {
		if (isPlaying) return;
		isPlaying = true;
		animationStep = 0;
		currentDomainIndex = 0;
		openChildren = [];
		expandedChild = undefined;
		animationLoop();
	}

	function pause() {
		isPlaying = false;
		clearTimeout(timeoutId);
	}

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
				if ($page.url.searchParams.has('animated')) {
					play();
				}
			});

		return () => {
			pause();
		};
	});
</script>

<svelte:head>
	<title>Tiles | {data.view.name}</title>
</svelte:head>

<h1>{data.view.name}</h1>

<div bind:clientWidth={innerWidth} bind:clientHeight={innerHeight} class="svg-container">
	{#if tree}
		<svg viewBox="0 0 {vbWidth} {vbHeight}">
			<TileTreeMap
				data={tree}
				width={vbWidth}
				height={vbHeight}
				open={true}
				showText={true}
				transitionMs={800}
				{openChildren}
				{expandedChild}
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
	.svg-container {
		height: 80svh;
	}
	svg {
		padding: 2%;
		width: 100%;
		height: 100%;
	}

	.controls {
		display: flex;
		justify-content: center;
		padding: 20px;
		border-top: 1px solid #ccc;
	}

	table {
		width: 100%;
		max-width: 600px;
		border-collapse: collapse;
	}

	th,
	td {
		padding: 8px 12px;
		text-align: left;
		border-bottom: 1px solid #ddd;
	}

	td:nth-child(2),
	td:nth-child(3),
	th:nth-child(2),
	th:nth-child(3) {
		text-align: center;
	}

	input[type='radio'],
	input[type='checkbox'] {
		cursor: pointer;
	}
</style>
