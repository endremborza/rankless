<script lang="ts">
	import { APP_NAME } from '$lib/constants';
	import type { PaperProfileResp } from '$lib/tree-types';
	import { buildPaperMap, stripHtml } from '$lib/utils/paper-helpers';
	import type { EntityPeersResp, AuthorMergeRequest } from '$lib/tree-types';
	import ImpactDag from '$lib/components/ImpactDag.svelte';

	export let data: {
		name: string;
		profile: PaperProfileResp | null;
		peersData: EntityPeersResp | null;
		semanticId: string;
		paperText: string;
		citeText: string;
		orcid: string;
		isOwner: boolean;
		disownedWids: number[];
		claimedDois: string[];
		mergedPairs: [number, number][];
		authorMergeRequests: AuthorMergeRequest[];
	};

	$: papers = data.profile?.papers.papers ?? [];
	$: entityAtts = data.profile?.papers.entityAtts ?? {};
	$: discAuthorNames = data.profile?.papers.discAuthorNames ?? {};
	$: authorsMeta = data.profile?.papers.authorsMeta ?? {};
	$: paperMap = data.profile ? buildPaperMap(papers) : {};

	$: dagEmpty =
		!data.profile ||
		data.profile.dag === 'Leaf' ||
		Object.keys((data.profile.dag as { Node: object }).Node ?? {}).length === 0;
</script>

<svelte:head>
	<title>{APP_NAME} | {stripHtml(data.name)} – Paper Profile</title>
	<meta
		name="description"
		content="Immediate impact for {stripHtml(data.name)} – {data.paperText}, {data.citeText}"
	/>
</svelte:head>

<div class="shadowy padded marged">
	<h2>Immediate Impact</h2>
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
	h2 {
		margin-bottom: 8px;
		text-align: center;
	}


</style>
