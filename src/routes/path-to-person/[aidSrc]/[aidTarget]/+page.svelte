<script lang="ts">
	import type * as tt from '$lib/tree-types';
	import * as tf from '$lib/tree-functions';
	import { BE_REMOTE_URL } from '$lib/constants';
	import { afterNavigate, replaceState } from '$app/navigation';
	import { onMount } from 'svelte';
	export let data: { srcAid: string; targetAid: string };

	type HitElem = { pathResp: tt.PathResp; hit: { pathUrl: string; title: string; doi: string } };

	let srcAid = data.srcAid;
	let targetAid = data.targetAid;
	let mounted = false;
	onMount(() => {
		mounted = true;
		reloadPaths(srcAid, targetAid);
	});
	$: reloadPaths(srcAid, targetAid);

	let hits: HitElem[] = [];
	async function reloadPaths(srcAid: string, targetAid: string) {
		if (!mounted) return;
		if (srcAid != '' && targetAid != '' && srcAid != 'src' && targetAid != 'target') {
			let newUrl = `/path-to-person/${srcAid}/${targetAid}`;
			replaceState(newUrl, {});
			let beBase = BE_REMOTE_URL;
			let viewUrl = tf.viewBeUrl(beBase, { rootType: 'authors', semanticId: targetAid });
			let hits = await fetch(viewUrl)
				.then((res) => res.json())
				.then((view: tt.View) => {
					let hits = [];
					for (const paper of view?.hitPapers || []) {
						if (paper.doi.length > 0) {
							let urlFriendlySemId = tf.urlFriendlify(paper.doi);
							let pathUrl = `${beBase}/path-to-paper/${srcAid}/${urlFriendlySemId}`;
							hits.push({ pathUrl, title: paper.name, doi: paper.doi });
						}
					}
					return hits;
				})
				.catch(() => []);
			let newHitList: HitElem[] = [];
			for (const hit of hits) {
				await fetch(hit.pathUrl)
					.then((res) => res.json())
					.then((pathResp: tt.PathResp) => {
						newHitList.push({ hit, pathResp });
					})
					.catch(() => {});
			}
			hits = newHitList;
		}
	}
</script>

<div class="container">
	<div class="control">
		<input type="text" bind:value={srcAid} />
		<input type="text" bind:value={targetAid} />
	</div>
	{#each hits as { hit, pathResp }}
		<h2><a href="https://doi.org/{hit.doi}">{hit.title}</a></h2>
	{/each}
</div>

<style>
	.container {
		max-width: 1200px;
		padding-top: 100px;
		margin: auto;
	}
</style>
