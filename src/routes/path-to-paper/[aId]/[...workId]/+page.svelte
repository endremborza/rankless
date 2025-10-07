<script lang="ts">
	import RefTreeVis from '$lib/components/RefTreeVis.svelte';
	import type { PathResp } from '$lib/tree-types';

	export let data: PathResp;
</script>

<div class="container">
	{#if data.paths == 'Leaf'}
		<h1>No Paths</h1>
	{:else}
		<h1>Paths</h1>
		<RefTreeVis
			refTree={data.paths}
			doiMap={data.doiMap}
			nameMap={data.nameMap}
			relWorks={data.relWorks}
		/>
	{/if}
</div>

<style>
	.container {
		max-width: 800px;
		padding-top: 100px;
		margin: auto;
	}
</style>
