<script lang="ts">
	import { APP_NAME } from '$lib/constants';
	import type { PaperProfileResp } from '$lib/tree-types';
	import { buildPaperMap, isAuthored } from '$lib/utils/paper-helpers';
	import PaperRainbow from '$lib/components/PaperRainbow.svelte';
	import ImpactDag from '$lib/components/ImpactDag.svelte';

	export let data: {
		name: string;
		profile: PaperProfileResp | null;
		semanticId: string;
		paperText: string;
		citeText: string;
	};

	$: papers = data.profile?.papers.papers ?? [];
	$: entityAtts = data.profile?.papers.entityAtts ?? {};
	$: discAuthorNames = data.profile?.papers.discAuthorNames ?? {};
	$: authorsMeta = data.profile?.papers.authorsMeta ?? {};
	$: authoredHitPapers = papers.filter(
		(p) => isAuthored(p, data.semanticId, entityAtts) && p.yearlyCites && p.yearlyCites.length > 0
	);
	$: paperMap = data.profile ? buildPaperMap(papers) : {};

	$: dagEmpty =
		!data.profile ||
		data.profile.dag === 'Leaf' ||
		Object.keys((data.profile.dag as { Node: object }).Node ?? {}).length === 0;
</script>

<svelte:head>
	<title>{APP_NAME} | {data.name} – Paper Profile</title>
	<meta
		name="description"
		content="Paper profile for {data.name} – {data.paperText}, {data.citeText}"
	/>
</svelte:head>

<div id="head" class="shadowy padded marged">
	<a href="/authors/{data.semanticId}" class="back-link">← Back to full profile</a>
	<h1>{data.name}</h1>
	<p class="stats">{data.paperText} · {data.citeText}</p>
</div>

{#if authoredHitPapers.length > 0}
	<div class="shadowy padded marged">
		<h2>Standout Papers</h2>
		<PaperRainbow papers={authoredHitPapers} {entityAtts} {discAuthorNames} />
	</div>
{/if}

<div class="shadowy padded marged">
	<h2>Citation Impact</h2>
	{#if dagEmpty}
		<p class="status">No citation impact paths found for this author.</p>
	{:else if data.profile}
		<ImpactDag
			dag={data.profile.dag}
			{paperMap}
			{entityAtts}
			{discAuthorNames}
			{authorsMeta}
			sourceAuthorSemId={data.semanticId}
			authorName={data.name}
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

	.status {
		opacity: 0.6;
		font-style: italic;
	}
</style>
