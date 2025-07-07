<script lang="ts">
	import { onMount } from 'svelte';
	import type * as tt from '$lib/tree-types';
	import * as tf from '$lib/tree-functions';
	import { BE_REMOTE_URL } from '$lib/constants';
	import PathLevelInfoBox from './PathLevelInfoBox.svelte';

	export let l1Type: tt.EntityType;
	export let flatOut: tt.LevelT;
	export let titlePrefix: string;
	export let semantifyer: (rt: tt.RootType, bd: string) => string;
	export let rootName = '';
	export let rootId: number;
	export let indsByEntityType: tt.IndsByEntityType;
	export let conf: tt.FullTreeConfig;
	export let treeSpecs: tt.TreeSpecs;
	export let infoPath: number[] = [];
	export let year = conf.year;
	export let resp: tt.TreeResponse | undefined = undefined;
	export let isSpec = false;
	export let treeId =
		treeSpecs.specs[conf.rootType][conf.treeId].breakdowns[0].attributeType == l1Type
			? conf.treeId
			: indsByEntityType[l1Type][0];

	let mounted = false;
	let selectedBreakdowns = tf.getDefaultBreakdowns(treeSpecs.specs[conf.rootType][treeId]);

	$: levelOptions = tf.fillBreakdownOptions(
		indsByEntityType[l1Type].map(
			(e) => [e, treeSpecs.specs[conf.rootType][e]] as [number, tt.TreeSpec]
		),
		1
	);
	$: currentTreeSpec = treeSpecs.specs[conf.rootType][treeId];

	function updateTreeId(bSelected: string[], bdOptions: tt.BreakdownOptions) {
		let bop = bSelected[0];
		let treeIds = bdOptions[bop]?.treeSpecs || [];
		if (treeIds.length == 0) {
			for (const [k, v] of Object.entries(bdOptions)) {
				if (v.treeSpecs.length > 0) {
					[bSelected[0], treeId] = [k, v.treeSpecs[0]];
				}
				return;
			}
		}
		if (!treeIds.includes(treeId)) {
			treeId = treeIds[0];
		}
	}

	function reloadResp(treeId: number, year: number, _rootId: number) {
		if (mounted == false) return;
		let newConf: tt.FullTreeConfig = { ...conf, treeId, year, wide: true };
		fetch(tf.treeBeUrl(BE_REMOTE_URL, newConf, 0)).then((res) => {
			res
				.json()
				.then((jsv: tt.TreeResponse) => {
					resp = jsv;
				})
				.catch((e) => {
					console.error('error', e);
				});
		});
	}

	function setNewFlout(resp: tt.TreeResponse | undefined, isSpec: boolean) {
		let newFlout = tf.flatFromResp(resp, isSpec, currentTreeSpec);
		if (newFlout != undefined) flatOut = newFlout;
	}

	onMount(() => {
		mounted = true;
		if (resp == undefined) {
			reloadResp(treeId, year, rootId);
		}
	});
	$: updateTreeId(selectedBreakdowns, levelOptions);
	$: setNewFlout(resp, isSpec);
	$: reloadResp(treeId, year, rootId);
	$: titleSuffix =
		selectedBreakdowns != undefined ? semantifyer(conf.rootType, selectedBreakdowns[0]) : '';
</script>

<h3>{titlePrefix} {titleSuffix} {rootName}</h3>

<span id="map-control-block">
	{#if Object.keys(levelOptions).length > 1}
		<select bind:value={selectedBreakdowns[0]} class="sel-base" aria-label="Breakdown selection">
			{#each Object.keys(levelOptions) as bd}
				<option value={bd}>
					{semantifyer(conf.rootType, bd)}
				</option>
			{/each}
		</select>
	{/if}
	Since
	<select bind:value={year} aria-label="Since year"
		>{#each treeSpecs.yearBreaks as y}
			<option>{y}</option>
		{/each}
	</select>
	<input type="checkbox" bind:checked={isSpec} /> Specialization
</span>
<slot />

<div id="map-hover">
	{#if resp != undefined}
		<PathLevelInfoBox
			path={infoPath}
			rootNode={resp.tree}
			initHeight={120}
			{rootName}
			treeSpec={currentTreeSpec}
			{rootId}
			attributeLabels={resp.atts}
		/>
	{/if}
</div>

<style>
	h3 {
		text-align: center;
	}

	#map-hover {
		position: relative;
		height: 160px;
		width: 100%;
	}

	#map-control-block {
		display: flex;
		flex-wrap: wrap;
		gap: var(--unified-padding);
		justify-content: center;
		width: 100%;
		margin-bottom: var(--unified-padding);
	}
</style>
