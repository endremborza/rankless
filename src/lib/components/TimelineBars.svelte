<script lang="ts">
	import { onMount } from 'svelte';

	import type * as tt from '$lib/tree-types';
	import * as tf from '$lib/tree-functions';
	import { BE_REMOTE_URL, COMPLETE_YEAR, LATEST_YEAR } from '$lib/constants';

	export let rootName = '';
	export let rootId: number;
	export let conf: tt.FullTreeConfig;
	export let treeSpecs: tt.TreeSpecs;

	let resp: tt.TreeResponse | undefined;
	onMount(() => {
		let treeId = treeSpecs.specs[conf.rootType].length - 1;
		let year = COMPLETE_YEAR;
		let newConf: tt.FullTreeConfig = { ...conf, treeId, year, wide: false };
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
	});

	function getEffs(l1Range: [number, number], l2range: [number, number], tree: tt.ResponseNode) {
		let out = {};
		let ov = 0;
		let o;
		for (let l1 = l1Range[0]; l1 <= l1Range[1]; l1++) {
			o = (tree.children || {})[l1 - COMPLETE_YEAR] || {};
			console.log(l1, o);
			ov += o.sourceCount || 0;
		}
		return ov;
	}

	let refStart = COMPLETE_YEAR;
	let refEnd = refStart + 5;

	let citStart = refStart;
	let citEnd = citStart + 5;
</script>

<input type="range" bind:value={refStart} min={COMPLETE_YEAR} max={LATEST_YEAR - 1} />
<input type="range" bind:value={refEnd} min={refStart} max={LATEST_YEAR - 1} />
<input type="range" bind:value={citStart} min={refStart} max={LATEST_YEAR - 1} />
<input type="range" bind:value={citEnd} min={citStart} max={LATEST_YEAR - 1} />

<p>
	{#if resp != undefined}
		{Object.keys(resp.tree.children || {}).map((e) => parseInt(e) + COMPLETE_YEAR)}
		{getEffs([refStart, refEnd], [citStart, citEnd], resp.tree)}
	{/if}
</p>

<style>
	p {
		padding: 20px;
	}
</style>
