<script lang="ts">
	import { APP_NAME } from '$lib/constants';
	import { prettifyRoot } from '$lib/text-format-util';

	import type * as tt from '$lib/tree-types';
	import * as tf from '$lib/tree-functions';
	import {
		isAuthored,
		fetchOaAbstract,
		htmlToText,
		mergeEntityAtts
	} from '$lib/utils/paper-helpers';
	import { afterNavigate } from '$app/navigation';

	import FullQc from '$lib/components/FullQc.svelte';
	import EntityHero from '$lib/components/EntityHero.svelte';
	import RandTreeLink from '$lib/components/RandTreeLink.svelte';
	import WorldMapSvg from '$lib/components/WorldMapSvg.svelte';
	import ConceptMap from '$lib/components/ConceptMap.svelte';
	import AuthorNetwork from '$lib/components/AuthorNetwork.svelte';
	import Toc from '$lib/components/Toc.svelte';
	import PaperRainbow from '$lib/components/PaperRainbow.svelte';
	import Peers from '$lib/components/Peers.svelte';
	import AllWorks from '$lib/components/AllWorks.svelte';
	import AuthorOwnerTools from '$lib/components/AuthorOwnerTools.svelte';
	import AuthorLedgerPanel from '$lib/components/AuthorLedgerPanel.svelte';
	import { createWorksLoader } from '$lib/utils/works-loader';
	import type { LedgerEvent, AppliedManifest } from '$lib/types/ledger';

	export let data: {
		view: tt.View;
		conf: tt.FullTreeConfig;
		selectionState: tt.BareNode;
		treeSpecs: tt.TreeSpecs;
		tree: tt.ResponseNode;
		atts: tt.AttributeLabels;
		svgLink: string;
		pngLink: string;
		shallowed: boolean;
		aboutParagraph: tt.AboutPara;
		metaDescriptions: string;
		paperText: string;
		citeText: string;
		prefixText: string;
		profile: tt.PaperProfileResp | null;
		peersData: tt.EntityPeersResp | null;
		ladder: tt.LadderData | null;
		initialPapers: tt.Paper[];
		initialEntityAtts: tt.EntityAttsForLinks;
		initialDiscAuthorNames: Record<string, string>;
		initialTotalPapers: number;
		initialWorksSliceEnd: number;
		isOwner: boolean;
		disownedWids: number[];
		claimedDois: string[];
		mergedPairs: [number, number][];
		authorMergeRequests: tt.AuthorMergeRequest[];
		ledgerEvents: LedgerEvent[];
		ledgerManifest: AppliedManifest;
	};

	$: isAuthor = data.conf.rootType === 'authors';
	$: hasPeers = (data.peersData?.peers.length ?? 0) > 0;
	$: isHitPaper = data.conf.rootType === 'hit-papers';

	let hitPaperAbstract: string | null = null;
	let abstractLoading = false;

	// Combined entity attribute maps (profile data + initial works batch); deep-merged so the
	// initial batch's smaller per-type maps don't clobber the profile's fuller ones.
	$: entityAtts = mergeEntityAtts(data.profile?.papers.entityAtts, data.initialEntityAtts);
	$: discAuthorNames = {
		...(data.profile?.papers.discAuthorNames ?? {}),
		...data.initialDiscAuthorNames
	} as Record<string, string>;

	$: papers = data.profile?.papers.papers ?? [];
	$: authoredHitPapers = papers.filter(
		(p) =>
			isAuthored(p, data.conf.semanticId, entityAtts) && p.yearlyCites && p.yearlyCites.length > 0
	);

	let disownedSet = new Set(data.disownedWids);
	let mergedPairsState = [...data.mergedPairs];
	afterNavigate(() => {
		disownedSet = new Set(data.disownedWids);
		mergedPairsState = [...data.mergedPairs];
		hitPaperAbstract = null;
		abstractLoading = isHitPaper;
		if (isHitPaper) {
			const sid = data.conf.semanticId;
			fetchOaAbstract(sid).then((result) => {
				// Ignore a slow fetch for a previous paper that resolves after we navigated away, so it
				// can't clobber the current paper's abstract or loading state.
				if (sid !== data.conf.semanticId) return;
				hitPaperAbstract = result;
				abstractLoading = false;
			});
		}
	});

	// One shared works loader feeds both the works table and the co-author network, seeded with the
	// SSR batch so the table renders instantly while the network can pull the full set on demand.
	const works = createWorksLoader();
	$: if (isAuthor)
		works.loadInitial(data.conf.semanticId, {
			papers: data.initialPapers,
			entityAtts,
			discAuthorNames,
			sliceEnd: data.initialWorksSliceEnd,
			totalPapers: data.initialTotalPapers
		});

	$: indsByEntityType = tf.getTreeIndsByEntityType(data.treeSpecs.specs[data.conf.rootType]);
	$: showsCountry = indsByEntityType.countries.length > 0;
	$: showsSubfields = indsByEntityType.subfields.length > 0;

	$: tocSections = [
		{ id: 'overview', label: 'Overview' },
		{ id: 'impact', label: 'Impact' },
		...(isAuthor && authoredHitPapers.length > 0 ? [{ id: 'papers', label: 'Hit Papers' }] : []),
		...(hasPeers ? [{ id: 'peers', label: 'Peers' }] : []),
		...(showsCountry ? [{ id: 'geography', label: 'Geography' }] : []),
		...(showsSubfields ? [{ id: 'research-space', label: 'Research Space' }] : []),
		...(isAuthor ? [{ id: 'network', label: 'Co-Authors' }] : []),
		...(isAuthor ? [{ id: 'works', label: 'Works' }] : [])
	];

	async function handleDisown(e: CustomEvent<number>) {
		const wid = e.detail;
		disownedSet = new Set([...disownedSet, wid]);
		const resp = await fetch('/api/papers/disown', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ wid })
		});
		if (!resp.ok) {
			disownedSet = new Set([...disownedSet].filter((w) => w !== wid));
		}
	}

	async function handleUndisown(e: CustomEvent<number>) {
		const wid = e.detail;
		disownedSet = new Set([...disownedSet].filter((w) => w !== wid));
		const resp = await fetch('/api/papers/disown', {
			method: 'DELETE',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ wid })
		});
		if (!resp.ok) {
			disownedSet = new Set([...disownedSet, wid]);
		}
	}

	async function handleMerge(e: CustomEvent<{ keep: number; drop: number }>) {
		const { keep, drop } = e.detail;
		mergedPairsState = [...mergedPairsState, [keep, drop]];
		await fetch('/api/papers/merge', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ wid_keep: keep, wid_drop: drop })
		});
	}

	async function handleUnmerge(e: CustomEvent<{ keep: number; drop: number }>) {
		const { keep, drop } = e.detail;
		mergedPairsState = mergedPairsState.filter(([k, d]) => !(k === keep && d === drop));
		await fetch('/api/papers/merge', {
			method: 'DELETE',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ wid_keep: keep, wid_drop: drop })
		});
	}
</script>

<svelte:head>
	<title>{APP_NAME} | {htmlToText(data.view.name)}</title>
	<meta name="description" content={data.metaDescriptions} />
	<meta property="og:type" content="website" />
	<meta property="og:site_name" content={APP_NAME} />
	<meta property="og:title" content="{htmlToText(data.view.name)} | {APP_NAME}" />
	<meta property="og:description" content={data.metaDescriptions} />
	<meta
		property="og:url"
		content={tf.externalEntityUrl(data.conf.rootType, data.conf.semanticId)}
	/>
	<meta property="og:image" content={data.pngLink} />
	<meta property="og:image:type" content="image/png" />
	<meta property="og:image:width" content="1200" />
	<meta property="og:image:height" content="630" />
	<meta name="twitter:card" content="summary_large_image" />
	<meta name="twitter:creator" content="@LearningCCL" />
	<meta name="twitter:title" content="{htmlToText(data.view.name)} | {APP_NAME}" />
	<meta name="twitter:description" content={data.metaDescriptions} />
	<meta name="twitter:image" content={data.pngLink} />
	<link rel="canonical" href={tf.externalEntityUrl(data.conf.rootType, data.conf.semanticId)} />
</svelte:head>

<section id="overview" class="shadowy padded marged main-block">
	<EntityHero
		view={data.view}
		rootType={data.conf.rootType}
		semanticId={data.conf.semanticId}
		peersData={data.peersData}
		ladder={data.ladder}
		citeText={data.citeText}
		hitPaperCount={authoredHitPapers.length}
		abstract={hitPaperAbstract}
		{abstractLoading}
	/>
</section>

<Toc sections={tocSections} />

<section id="impact" class="shadowy padded marged main-block">
	<!-- Key on entity identity so navigating between entities tears the tree down and rebuilds it
	     from the fresh props. Reusing the instance left FullQc's local `currentTreeSpec` seeded from
	     a one-time prop default, so a new entity's tree rendered against the old spec → first-level
	     names resolved against the wrong entity type → "Unknown". The year filter mutates conf in
	     place (same identity), so it stays within one instance and still hot-reloads via loadNewQc. -->
	{#key `${data.conf.rootType}/${data.conf.semanticId}`}
		<FullQc
			rootName={data.view.name}
			prefixText={data.prefixText}
			selectedQcRootId={data.view.dmId}
			conf={data.conf}
			selectionState={data.selectionState}
			treeSpecs={data.treeSpecs}
			attributeLabels={data.atts}
			completeTree={data.tree}
			shallowed={data.shallowed}
			shoPathLevelInfo={!isHitPaper}
		/>
	{/key}
</section>

{#if isAuthor && authoredHitPapers.length > 0}
	<section id="papers" class="shadowy padded marged main-block">
		<h2>Hit Papers</h2>
		<PaperRainbow
			papers={authoredHitPapers}
			{entityAtts}
			{discAuthorNames}
			treeSpecs={data.treeSpecs}
		/>
	</section>
{/if}

{#if hasPeers && data.peersData}
	<section id="peers" class="shadowy padded marged main-block">
		<h2>Peers</h2>
		<Peers data={data.peersData} rootType={data.conf.rootType} />
	</section>
{/if}

{#if showsCountry}
	<section id="geography" class="shadowy padded marged main-block heighted">
		<WorldMapSvg
			rootId={data.view.dmId}
			{indsByEntityType}
			rootName={data.view.name}
			conf={data.conf}
			treeSpecs={data.treeSpecs}
		/>
	</section>
{/if}

{#if showsSubfields}
	<section id="research-space" class="shadowy padded marged main-block heighted">
		<ConceptMap
			rootId={data.view.dmId}
			{indsByEntityType}
			rootName={data.view.name}
			conf={data.conf}
			treeSpecs={data.treeSpecs}
		/>
	</section>
{/if}

{#if isAuthor}
	<section id="network" class="shadowy padded marged main-block">
		<AuthorNetwork
			authors={data.view.relations['paper-authors'] ?? []}
			edgeWeights={data.view.authorNetwork}
			rootName={data.view.name}
			heroSemanticId={data.conf.semanticId}
			{works}
		/>
	</section>

	<section id="works" class="shadowy padded marged main-block">
		<h2>All Works</h2>

		{#if data.isOwner}
			<AuthorOwnerTools
				semanticId={data.conf.semanticId}
				claimedDois={data.claimedDois}
				authorMergeRequests={data.authorMergeRequests}
			/>
		{/if}

		<AllWorks
			{works}
			disownedWids={disownedSet}
			mergedPairs={mergedPairsState}
			isOwner={data.isOwner}
			on:disown={handleDisown}
			on:undisown={handleUndisown}
			on:merge={handleMerge}
			on:unmerge={handleUnmerge}
		/>

		{#if data.isOwner}
			<AuthorLedgerPanel events={data.ledgerEvents} manifest={data.ledgerManifest} />
		{/if}
	</section>
{/if}

<section id="similars" class="shadowy padded marged">
	<div class="about-seo">
		<h3>About {@html data.view.name}</h3>
		<p>{@html data.aboutParagraph.prefix}. {@html data.aboutParagraph.postText}</p>
	</div>
	<p>
		Rankless uses publication and citation data sourced from OpenAlex, an open and comprehensive
		bibliographic database. While OpenAlex provides broad and valuable coverage of the global
		research landscape, it—like all bibliographic datasets—has inherent limitations. These include
		incomplete records, variations in author disambiguation, differences in journal indexing, and
		delays in data updates. As a result, some metrics and network relationships displayed in
		Rankless may not fully capture the entirety of a scholar's output or impact.
	</p>
	{#if data.aboutParagraph.footText.length > 0}<p>{@html data.aboutParagraph.footText}</p>{/if}
	<h3>Explore {prettifyRoot(data.conf.rootType)} with similar magnitude of impact</h3>
	<div class="similars-grid">
		{#each data.view.similars as sim, __i (__i)}
			<span>
				<RandTreeLink
					semanticId={sim.semanticId}
					name={sim.name}
					rootType={data.conf.rootType}
					treeSpecs={data.treeSpecs}
				/>
			</span>
		{/each}
	</div>
</section>

<style>
	.heighted {
		display: flex;
		justify-content: space-between;
		align-items: center;
		flex-wrap: wrap;
	}

	#overview {
		margin-top: var(--unified-margin);
		margin-bottom: var(--unified-margin);
	}

	.about-seo {
		opacity: 0.55;
		font-size: var(--text-sm);
		line-height: var(--lh-body);
		margin-bottom: 24px;
	}

	.about-seo h3 {
		text-align: left;
		font-size: var(--text-base);
		opacity: 0.85;
		margin-bottom: 4px;
	}

	.main-block {
		margin-bottom: 0px;
	}

	#similars {
		margin-bottom: 40px;
	}

	.similars-grid {
		width: 100%;
		padding-top: 28px;
		padding-bottom: 48px;
		display: flex;
		flex-wrap: wrap;
		justify-content: space-evenly;
		align-items: stretch;
		gap: 40px;
	}

	.similars-grid > span {
		min-width: 180px;
		flex: 1 0 21%;
		padding: 6px;
		border-bottom: solid var(--color-theme-blue) 3px;
		background: rgba(var(--color-range-15), 0.1);
	}

	h2 {
		margin-bottom: 8px;
		text-align: center;
	}

	section {
		scroll-margin-top: 90px;
	}
</style>
