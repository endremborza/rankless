<script lang="ts">
	import type { RefTree } from '$lib/tree-types';
	export let refTree: { Node: Record<number, RefTree> };
	export let nameMap: Record<number, string>;
	export let doiMap: Record<number, string>;
	export let relWorks: number[];
</script>

<ul>
	{#each Object.entries(refTree.Node) as [k, v]}
		<li>
			<div class={relWorks.includes(parseInt(k)) ? 'irrelevant' : 'relevant'}>
				{#if doiMap[k] != undefined}
					<a href="https://doi.org/{doiMap[k]}">{nameMap[k]}</a>
				{:else}
					<span>{nameMap[k]}</span>
				{/if}
			</div>

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
	}
	.irrelevant {
		font-size: 0.8rem;
		font-weight: 800;
	}
</style>
