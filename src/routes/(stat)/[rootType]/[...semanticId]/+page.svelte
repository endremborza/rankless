<script lang="ts">
	import { APP_NAME, REL_TYPES } from '$lib/constants';
	import { prettifyRoot, pluralize } from '$lib/text-format-util';

	import type * as tt from '$lib/tree-types';
	import * as tf from '$lib/tree-functions';
	import { isAuthored, fetchOaAbstract, htmlToText } from '$lib/utils/paper-helpers';
	import { onMount } from 'svelte';

	import FullQc from '$lib/components/FullQc.svelte';
	import YearTicks from '$lib/components/YearTicks.svelte';
	import RandTreeLink from '$lib/components/RandTreeLink.svelte';
	import HoverBlock from '$lib/components/HoverBlock.svelte';
	import WorldMapSvg from '$lib/components/WorldMapSvg.svelte';
	import ConceptMap from '$lib/components/ConceptMap.svelte';
	import AuthorNetwork from '$lib/components/AuthorNetwork.svelte';
	import Toc from '$lib/components/Toc.svelte';
	import PaperRainbow from '$lib/components/PaperRainbow.svelte';
	import Peers from '$lib/components/Peers.svelte';
	import AllWorks from '$lib/components/AllWorks.svelte';
	import AuthorOwnerTools from '$lib/components/AuthorOwnerTools.svelte';
	import AuthorLedgerPanel from '$lib/components/AuthorLedgerPanel.svelte';
	import type { LedgerEvent, AppliedManifest } from '$lib/types/ledger';

	export let data: {
		view: tt.View;
		conf: tt.FullTreeConfig;
		selectionState: tt.BareNode;
		treeSpecs: tt.TreeSpecs;
		tree: tt.ResponseNode;
		atts: tt.AttributeLabels;
		svgLink: string;
		shallowed: boolean;
		aboutParagraph: tt.AboutPara;
		metaDescriptions: string;
		paperText: string;
		citeText: string;
		prefixText: string;
		profile: tt.PaperProfileResp | null;
		peersData: tt.EntityPeersResp | null;
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

	let showIndexedCiteText = false;
	let ticksHeight: number;

	$: isAuthor = data.conf.rootType === 'authors';
	$: hasPeers = (data.peersData?.peers.length ?? 0) > 0;
	$: isHitPaper = data.conf.rootType === 'hit-papers';
	// $: rawPapers = isAuthor ? parseInt(data.view.meta?.rawPapers ?? '0') || 0 : 0;

	let hitPaperAbstract: string | null = null;
	let abstractExpanded = false;
	let mounted = false;
	onMount(() => {
		mounted = true;
	});
	$: if (mounted && isHitPaper) {
		hitPaperAbstract = null;
		fetchOaAbstract(data.conf.semanticId).then((result) => {
			hitPaperAbstract = result;
		});
	} else {
		hitPaperAbstract = null;
	}
	$: rawCites = isAuthor ? parseInt(data.view.meta?.rawCites ?? '0') || 0 : 0;

	// Combined entity attribute maps (profile data + initial works batch)
	$: entityAtts = {
		...(data.profile?.papers.entityAtts ?? {}),
		...data.initialEntityAtts
	} as tt.EntityAttsForLinks;
	$: discAuthorNames = {
		...(data.profile?.papers.discAuthorNames ?? {}),
		...data.initialDiscAuthorNames
	} as Record<string, string>;

	$: papers = data.profile?.papers.papers ?? [];
	$: authoredHitPapers = papers.filter(
		(p) =>
			isAuthored(p, data.conf.semanticId, entityAtts) && p.yearlyCites && p.yearlyCites.length > 0
	);

	$: disownedSet = new Set(data.disownedWids);
	$: mergedPairsState = [...data.mergedPairs];

	function getAuthorStats(view: tt.View) {
		let authorNames: string[] = [];
		let authorScores: number[] = [];
		for (const rel of view.primeRelations) {
			if (REL_TYPES[rel.relType] == 'paper-authors') {
				authorNames.push(rel.name);
				authorScores.push(rel.score);
			}
		}
		return { authorNames, authorScores, edgeWeights: view.authorNetwork };
	}

	$: indsByEntityType = tf.getTreeIndsByEntityType(data.treeSpecs.specs[data.conf.rootType]);
	$: showsCountry = indsByEntityType.countries.length > 0;
	$: showsSubfields = indsByEntityType.subfields.length > 0;
	$: authorStats = getAuthorStats(data.view);

	$: tocSections = [
		{ id: 'overview', label: 'Overview' },
		{ id: 'impact', label: 'Impact' },
		...(isAuthor && authoredHitPapers.length > 0
			? [{ id: 'papers', label: 'Standout Papers' }]
			: []),
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
	<meta name="twitter:card" content="summary" />
	<meta name="twitter:creator" content="@LearningCCL" />
	<meta name="description" content={data.metaDescriptions} />
	<meta property="og:image" content={data.svgLink} />
	<meta property="og:title" content="{data.view.name} | {APP_NAME}" />
	<link rel="canonical" href={tf.externalEntityUrl(data.conf.rootType, data.conf.semanticId)} />
</svelte:head>

<section id="overview" class="shadowy padded marged main-block">
	<div id="name-block">
		<HoverBlock
			show={showIndexedCiteText}
			style={'top: 20svh; left:20vw; width: 60vw;max-width: 550px'}
		>
			Citations made by non-retracted papers categorized as "article", "book", or "review" that have
			received at least one citation.
		</HoverBlock>
		<!-- svelte-ignore a11y-mouse-events-have-key-events -->
		<div id="nametag">
			<h1>{@html data.view.name}</h1>
			{#if isHitPaper}
				<div>
					<span>{data.citeText}</span>
				</div>
			{:else if rawCites > 0}
				<div>
					<span>{pluralize('total citation', rawCites)}</span>
					{#if isAuthor && authoredHitPapers.length > 0}
						·
						<a href="#papers">{pluralize('hit paper', authoredHitPapers.length)}</a>
					{/if}
					<br />
					<span class="indexed-subtext"
						>{pluralize('paper', data.view.papers)}, {pluralize('citation', data.view.citations)}
						<a
							on:mouseover={() => {
								showIndexedCiteText = true;
							}}
							on:mouseleave={() => {
								showIndexedCiteText = false;
							}}
							href="/#indexed-citation"
							target="blank_">indexed</a
						></span
					>
				</div>
			{:else}
				<div>
					<span>{data.paperText}</span>
					and
					<span
						><a
							on:mouseover={() => {
								showIndexedCiteText = true;
							}}
							on:mouseleave={() => {
								showIndexedCiteText = false;
							}}
							href="/#indexed-citation"
							target="blank_">{data.citeText}</a
						></span
					>
				</div>
			{/if}
		</div>
		{#if isHitPaper}
			<details id="abstract" bind:open={abstractExpanded}>
				<summary><h2>Abstract</h2></summary>
				{#if hitPaperAbstract}
					<p class="abstract-text" class:abstract-truncated={!abstractExpanded}>
						{hitPaperAbstract}
					</p>
				{:else}
					<p class="abstract-loading">loading...</p>
				{/if}
			</details>
		{/if}
		<div id="about">
			<h2>About</h2>
			<div>
				{@html data.aboutParagraph.prefix}.
				{@html data.aboutParagraph.postText}
			</div>
		</div>
	</div>
	<div id="era">
		<h2>In The Last Decade</h2>
		<div bind:clientHeight={ticksHeight}>
			<YearTicks
				bottomStacks={data.view.yearlyPapers}
				topStacks={data.view.yearlyCites}
				fullHeight={ticksHeight}
				showBottom={!isHitPaper}
			/>
		</div>
		{#if isHitPaper}
			{@const doi = !data.conf.semanticId.startsWith('W') ? data.conf.semanticId : null}
			<a
				href={doi ? `https://doi.org/${doi}` : `https://openalex.org/${data.conf.semanticId}`}
				target="_blank"
				rel="noopener"
				class="dag-link">{doi ? `doi.org/${doi}` : 'OpenAlex'} →</a
			>
		{/if}
	</div>
</section>

<Toc sections={tocSections} />

<section id="impact" class="shadowy padded marged main-block">
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
	<section id="network" class="shadowy padded marged main-block heighted">
		<AuthorNetwork
			nodes={authorStats.authorNames}
			edgeWeights={authorStats.edgeWeights}
			nodeIntensities={authorStats.authorScores}
			rootName={data.view.name}
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
			semanticId={data.conf.semanticId}
			{entityAtts}
			{discAuthorNames}
			initialPapers={data.initialPapers}
			initialSliceEnd={data.initialWorksSliceEnd}
			initialTotalPapers={data.initialTotalPapers}
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
		{#each data.view.similars as sim}
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

	@media (max-width: 800px) {
		#era > div {
			width: 100%;
		}
	}

	@media (min-width: 801px) {
		#overview {
			display: flex;
			flex-wrap: wrap;
			align-items: stretch;
			gap: 40px;
		}
	}

	#overview {
		margin-top: var(--unified-margin);
		margin-bottom: var(--unified-margin);
	}

	#name-block {
		flex: 8;
	}

	#era {
		flex: 4;
		display: flex;
		flex-direction: column;
		justify-content: space-evenly;
	}

	#era > div {
		aspect-ratio: 2.5;
	}

	.dag-link {
		font-size: var(--text-sm);
		opacity: 0.4;
		text-decoration: none;
		color: var(--color-text);
		transition: opacity 0.15s;
		padding: 2px 0;
	}

	.dag-link:hover {
		opacity: 0.8;
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

	.indexed-subtext {
		opacity: 0.8;
		font-size: var(--text-sm);
	}

	h2 {
		margin-bottom: 8px;
		text-align: center;
	}

	#abstract summary {
		cursor: pointer;
		list-style: none;
	}

	#abstract summary::-webkit-details-marker {
		display: none;
	}

	#abstract summary h2 {
		display: inline;
		font-size: var(--text-sm);
		font-weight: normal;
		opacity: 0.55;
	}

	#abstract p {
		font-size: var(--text-base);
		line-height: var(--lh-body);
		opacity: 0.85;
	}

	.abstract-text.abstract-truncated {
		display: -webkit-box;
		-webkit-line-clamp: 4;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.abstract-loading {
		opacity: 0.35;
		font-size: var(--text-sm);
	}

	section {
		scroll-margin-top: 90px;
	}
</style>
