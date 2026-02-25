<script lang="ts">
	import { APP_NAME } from '$lib/constants';
	import type { View, PathToPapersResp } from '$lib/tree-types';
	import PaperRainbow from '$lib/components/PaperRainbow.svelte';
	import ImpactDag from '$lib/components/ImpactDag.svelte';

	export let data: {
		view: View;
		dagResp: PathToPapersResp | null;
		semanticId: string;
		paperText: string;
		citeText: string;
	};

	$: dagEmpty =
		!data.dagResp ||
		data.dagResp.dag === 'Leaf' ||
		Object.keys((data.dagResp.dag as { Node: object }).Node ?? {}).length === 0;
</script>

<svelte:head>
	<title>{APP_NAME} | {data.view.name} – Impact Graph</title>
	<meta
		name="description"
		content="Top papers and citation impact graph for {data.view.name} – {data.paperText}, {data.citeText}"
	/>
</svelte:head>

<div id="head" class="shadowy padded marged">
	<a href="/authors/{data.semanticId}" class="back-link">← Back to full profile</a>
	<h1>{data.view.name}</h1>
	<p class="stats">{data.paperText} · {data.citeText}</p>
</div>

{#if data.view.hitPapers.length > 0}
	<div class="shadowy padded marged">
		<h2>Top Papers</h2>
		<PaperRainbow papers={data.view.hitPapers} />
	</div>
{/if}

<div class="shadowy padded marged">
	<h2>Citation Impact Graph</h2>
	<p class="section-desc">
		High-impact papers that build on <strong>{data.view.name}</strong>'s work, connected through the
		citation network.
	</p>

	{#if dagEmpty}
		<p class="status">No citation impact paths found for this author.</p>
	{:else if data.dagResp}
		<ImpactDag
			dag={data.dagResp.dag}
			nameMap={data.dagResp.nameMap}
			doiMap={data.dagResp.doiMap}
			hitWids={data.dagResp.hitWids}
		/>
	{/if}
</div>

<style>
	.back-link {
		font-size: 0.8rem;
		opacity: 0.6;
		transition: opacity 0.15s;
	}

	.back-link:hover {
		opacity: 1;
	}

	h1 {
		margin-top: 4px;
		margin-bottom: 4px;
	}

	.stats {
		opacity: 0.6;
		margin: 0;
	}

	h2 {
		margin-bottom: 8px;
	}

	.section-desc {
		opacity: 0.7;
		margin-bottom: 20px;
	}

	.status {
		opacity: 0.6;
		font-style: italic;
	}
</style>
