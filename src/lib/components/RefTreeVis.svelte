<script lang="ts">
	import type { RefTree } from '$lib/tree-types';
	export let refTree: { Node: Record<number, RefTree> };
	export let nameMap: Record<number, string>;
	export let doiMap: Record<number, string>;
	export let relWorks: number[];

	function getClass(k, relWorks) {
		return relWorks.includes(parseInt(k)) ? 'relevant' : 'irrelevant';
	}
</script>

<ul>
	{#each Object.entries(refTree.Node) as [k, v]}
		<li>
			{#if doiMap[k] != undefined}
				<a href="https://doi.org/{doiMap[k]}" class={getClass(k, relWorks)}>{nameMap[k]}</a>
			{:else}
				<span class={getClass(k, relWorks)}>{nameMap[k]}</span>
			{/if}
			{k}
			{relWorks.includes(parseInt(k))}
			{#if relWorks.includes(parseInt(k))}
				THIS
			{/if}
			{#if v != 'Leaf'}
				<svelte:self refTree={v} {nameMap} {doiMap} {relWorks} />
			{/if}
		</li>
	{/each}
</ul>

<style>
	.relevant {
		font-size: 1.2rem;
		font-weight: 800;
		padding: 4px;
	}
	.irrelevant {
		font-size: 0.8rem;
		font-weight: 400;
	}
</style>
