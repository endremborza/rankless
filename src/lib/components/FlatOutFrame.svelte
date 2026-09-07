<script lang="ts">
	import { onMount } from 'svelte';
	import type * as tt from '$lib/tree-types';
	import * as tf from '$lib/tree-functions';
	import { createTreeLoader } from '$lib/utils/tree-loader';
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
	export let treeId: number;
	export let backupNames: Record<number, string> = {};
	export let showPaper = false;
	export let showInfobox = true;

	let mounted = false;
	let selectedBreakdowns = tf.getDefaultBreakdowns(treeSpecs.specs[conf.rootType][treeId]);
	const treeLoader = createTreeLoader();

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

	async function reloadResp(
		conf: tt.FullTreeConfig,
		treeId: number,
		year: number,
		_rootId: number
	) {
		if (!mounted) return;
		const jsv = await treeLoader.load({ ...conf, treeId, year, wide: true }, 0);
		if (!jsv) return;
		infoPath = [];
		resp = jsv;
	}

	function setNewFlout(resp: tt.TreeResponse | undefined, isSpec: boolean, treeSpec: tt.TreeSpec) {
		if (treeSpec == undefined) return;
		let newFlout = tf.flatFromResp(resp, isSpec, treeSpec);
		if (newFlout != undefined) flatOut = newFlout;
	}

	onMount(async () => {
		mounted = true;
		if (resp == undefined) {
			await reloadResp(conf, treeId, year, rootId);
		}
	});
	$: updateTreeId(selectedBreakdowns, levelOptions);
	$: setNewFlout(resp, isSpec, currentTreeSpec);
	$: reloadResp(conf, treeId, year, rootId);
	$: titleSuffix =
		selectedBreakdowns != undefined ? semantifyer(conf.rootType, selectedBreakdowns[0]) : '';
</script>

<div class="papered-figure-container">
	<div class="figure-container frame-top-half">
		<h3>{titlePrefix} {titleSuffix} {@html rootName}</h3>
		<div class="control-block">
			{#if Object.keys(levelOptions).length > 1}
				<select
					bind:value={selectedBreakdowns[0]}
					class="sel-base"
					aria-label="Breakdown selection"
				>
					{#each Object.keys(levelOptions) as bd, __i (__i)}
						<option value={bd}>
							{semantifyer(conf.rootType, bd)}
						</option>
					{/each}
				</select>
			{/if}
			{#if tf.hasYearFilter(conf.rootType)}
				Since
				<select bind:value={year} aria-label="Since year"
					>{#each treeSpecs.yearBreaks as y, __i (__i)}
						<option>{y}</option>
					{/each}
				</select>
			{/if}
			<input type="checkbox" bind:checked={isSpec} /> Specialization
		</div>
		<slot />
	</div>
	{#if showInfobox}
		<div class="infobox-container">
			{#if resp != undefined}
				<PathLevelInfoBox
					path={infoPath}
					rootNode={resp.tree}
					{rootName}
					treeSpec={currentTreeSpec}
					{rootId}
					attributeLabels={resp.atts}
					{backupNames}
					hasSpaceForPaper={true}
					bind:showPaper
				/>
			{/if}
		</div>
	{/if}
</div>

<style>
	h3 {
		text-align: center;
	}

	.frame-top-half {
		display: flex;
		flex-direction: column;
		justify-content: space-between;
	}

	.control-block {
		display: flex;
		flex-wrap: wrap;
		gap: var(--unified-padding);
		justify-content: center;
		width: 100%;
		margin-bottom: var(--unified-padding);
	}
</style>
