<script lang="ts">
	import type { PathResp } from '$lib/tree-types';
	import RefTreeTable from '$lib/components/RefTreeTable.svelte';

	export let data: PathResp;
</script>

<div class="container shadowy padded marged">
	<h1>Citation Paths</h1>
	<p class="subtitle">from <strong>{data.srcName}</strong> to <strong>{data.targetName}</strong></p>

	{#if data.paths.length === 0}
		<p class="empty">No citation paths found.</p>
	{:else}
		{#each data.paths as pathEntry}
			<div class="path-block">
				<h2>
					{#if pathEntry.doi}
						<a href="https://doi.org/{pathEntry.doi}" target="_blank">{pathEntry.title}</a>
					{:else}
						{pathEntry.title}
					{/if}
					{#if pathEntry.year}
						<span class="year">({pathEntry.year})</span>
					{/if}
				</h2>
				<RefTreeTable
					tree={pathEntry.tree}
					nameMap={data.nameMap}
					doiMap={data.doiMap}
					relWorks={data.relWorks}
				/>
			</div>
		{/each}
	{/if}
</div>

<style>
	.container {
		max-width: 1100px;
		margin: 80px auto 40px;
	}

	.subtitle {
		margin-bottom: 32px;
		opacity: 0.7;
	}

	.empty {
		opacity: 0.5;
	}

	.path-block {
		margin-bottom: 40px;
	}

	.year {
		font-weight: normal;
		opacity: 0.6;
		font-size: 0.85em;
	}

	h2 {
		margin-bottom: 8px;
	}
</style>
