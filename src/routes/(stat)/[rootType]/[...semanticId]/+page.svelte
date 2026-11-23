<script lang="ts">
	import type { AppliedManifest } from '$lib/wire/rankless_rs/user_ledger';
	import {
		TREE_SPECS,
		type EntityPeersResp,
		type LadderResp,
		type PaperOut,
		type PaperSetResp,
		type ViewResult
	} from '$lib/wire/rankless_server/responses';
	import type { AttributeLabels, EntityAttsForLinks } from '$lib/wire/rankless_trees/io';
	import { APP_NAME } from '$lib/constants';
	import { CARD_H, CARD_W } from '$lib/utils/cards';
	import { prettifyRoot } from '$lib/text-format-util';

	import type * as tt from '$lib/tree-types';
	import * as tf from '$lib/tree-functions';
	import { fetchOaAbstract, htmlToText, mergeEntityAtts } from '$lib/utils/paper-helpers';
	import { fetchImpactHighlights } from '$lib/utils/impact-highlights';
	import { afterNavigate, invalidateAll } from '$app/navigation';

	import FullQc from '$lib/components/FullQc.svelte';
	import EntityHero from '$lib/components/EntityHero.svelte';
	import ProfileDisclaimer from '$lib/components/ProfileDisclaimer.svelte';
	import RandTreeLink from '$lib/components/RandTreeLink.svelte';
	import WorldMapSvg from '$lib/components/WorldMapSvg.svelte';
	import ConceptMap from '$lib/components/ConceptMap.svelte';
	import AuthorNetwork from '$lib/components/AuthorNetwork.svelte';
	import Toc from '$lib/components/Toc.svelte';
	import PaperRainbow from '$lib/components/PaperRainbow.svelte';
	import ImpactHighlights from '$lib/components/ImpactHighlights.svelte';
	import ViewToggle from '$lib/components/ViewToggle.svelte';
	import type { ImpactHighlightsResp } from '$lib/wire/rankless_server/highlights';
	import Peers from '$lib/components/Peers.svelte';
	import AllWorks from '$lib/components/AllWorks.svelte';
	import AuthorLedgerPanel from '$lib/components/AuthorLedgerPanel.svelte';
	import EmailPreferences from '$lib/components/EmailPreferences.svelte';
	import { createWorksLoader } from '$lib/utils/works-loader';
	import { createStaleGuard } from '$lib/utils/stale-guard';
	import { createLedgerClient, type WriteOutcome } from '$lib/utils/ledger-client';
	import {
		pendingDisown,
		pendingMerge,
		withEdits,
		type WorksEdit
	} from '$lib/utils/ledger-effective';
	import type { LedgerEvent } from '$lib/types/ledger';

	export let data: {
		view: ViewResult;
		conf: tt.FullTreeConfig;
		selectionState: tt.BareNode;
		tree: tt.ResponseNode;
		atts: AttributeLabels;
		pngLink: string;
		shallowed: boolean;
		aboutParagraph: tt.AboutPara;
		metaDescriptions: string;
		paperText: string;
		citeText: string;
		prefixText: string;
		disclaimer: string | null;
		hits: PaperSetResp | null;
		peersData: EntityPeersResp | null;
		ladder: LadderResp | null;
		initialPapers: PaperOut[];
		initialEntityAtts: EntityAttsForLinks;
		initialDiscAuthorNames: Record<string, string>;
		initialTotalPapers: number;
		initialWorksSliceEnd: number;
		isOwner: boolean;
		disownedWids: number[];
		mergedPairs: [number, number][];
		ledgerEvents: LedgerEvent[];
		ledgerManifest: AppliedManifest;
	};

	$: isAuthor = data.conf.rootType === 'authors';
	$: entityKey = `${data.conf.rootType}/${data.conf.semanticId}`;
	$: hasPeers = (data.peersData?.peers.length ?? 0) > 0;
	$: isHitPaper = data.conf.rootType === 'hit-papers';

	let hitPaperAbstract: string | null = null;
	let abstractLoading = false;

	// Combined entity attribute maps (hit papers + initial works batch); deep-merged so the
	// initial batch's smaller per-type maps don't clobber the hit papers' fuller ones.
	$: entityAtts = mergeEntityAtts(data.hits?.entityAtts, data.initialEntityAtts);
	$: discAuthorNames = {
		...(data.hits?.discAuthorNames ?? {}),
		...data.initialDiscAuthorNames
	} as Record<string, string>;

	$: authoredHitPapers = (data.hits?.papers ?? []).filter(
		(p) => p.yearlyCites && p.yearlyCites.length > 0
	);
	let highlights: ImpactHighlightsResp | null = null;
	$: hasHighlights = isAuthor && !!highlights && highlights.highlights.length > 0;
	let impactView: 'breakdown' | 'highlights' = 'breakdown';
	$: showHighlights = impactView === 'highlights' && hasHighlights;

	let inFlight: WorksEdit[] = [];
	$: worksHidden = withEdits(data.disownedWids, data.mergedPairs, inFlight);
	const ledger = createLedgerClient(invalidateAll);
	function track(edit: WorksEdit, write: Promise<WriteOutcome>) {
		inFlight = [...inFlight, edit];
		write.then(() => (inFlight = inFlight.filter((e) => e !== edit)));
	}
	const claimNavigation = createStaleGuard();
	afterNavigate(() => {
		const isCurrent = claimNavigation();
		hitPaperAbstract = null;
		highlights = null;
		impactView = 'breakdown';
		abstractLoading = isHitPaper;
		if (isHitPaper) {
			fetchOaAbstract(data.conf.semanticId).then((result) => {
				if (!isCurrent()) return;
				hitPaperAbstract = result;
				abstractLoading = false;
			});
		}
		if (isAuthor) {
			fetchImpactHighlights(data.conf.semanticId).then((result) => {
				if (isCurrent()) highlights = result;
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

	$: indsByEntityType = tf.getTreeIndsByEntityType(TREE_SPECS.specs[data.conf.rootType]);
	$: showsCountry = indsByEntityType.countries.length > 0;
	$: showsSubfields = indsByEntityType.subfields.length > 0;

	$: tocSections = [
		{ id: 'overview', label: 'Overview' },
		{ id: 'impact', label: 'Impact' },
		...(isAuthor && authoredHitPapers.length > 0 ? [{ id: 'hits', label: 'Hit Papers' }] : []),
		...(hasPeers ? [{ id: 'peers', label: 'Peers' }] : []),
		...(showsCountry ? [{ id: 'geography', label: 'Geography' }] : []),
		...(showsSubfields ? [{ id: 'research-space', label: 'Research Space' }] : []),
		...(isAuthor ? [{ id: 'network', label: 'Co-Authors' }] : []),
		...(isAuthor ? [{ id: 'works', label: 'Works' }] : [])
	];

	function handleDisown(e: CustomEvent<number>) {
		const wid = e.detail;
		track({ wid, hidden: true }, ledger.post({ kind: 'disown_paper', wid }));
	}

	function handleUndisown(e: CustomEvent<number>) {
		const wid = e.detail;
		track(
			{ wid, hidden: false },
			ledger.withdrawFound(() => pendingDisown(data.ledgerEvents, wid))
		);
	}

	function handleMerge(e: CustomEvent<{ keep: number; drop: number }>) {
		const { keep, drop } = e.detail;
		track(
			{ keep, drop, hidden: true },
			ledger.post({ kind: 'merge_papers', keep: { wid: keep }, drop: { wid: drop } })
		);
	}

	function handleUnmerge(e: CustomEvent<{ keep: number; drop: number }>) {
		const { keep, drop } = e.detail;
		track(
			{ keep, drop, hidden: false },
			ledger.withdrawFound(() => pendingMerge(data.ledgerEvents, keep, drop))
		);
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
	<meta property="og:image:width" content={String(CARD_W)} />
	<meta property="og:image:height" content={String(CARD_H)} />
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
	<ProfileDisclaimer text={data.disclaimer} />
	{#if data.isOwner}<EmailPreferences />{/if}
</section>

<Toc sections={tocSections} />

<section id="impact" class="shadowy padded marged main-block">
	{#if hasHighlights}
		<header class="impact-head">
			<h3>Impact</h3>
			<ViewToggle
				options={[
					['breakdown', 'breakdown'],
					['highlights', 'highlights']
				]}
				bind:value={impactView}
			/>
		</header>
	{/if}
	{#if showHighlights && highlights}
		<ImpactHighlights resp={highlights} authorName={data.view.name} />
	{/if}
	<!-- Hidden rather than unmounted under the highlights, since a remount would reseed it from the
	     page's first tree. -->
	<div hidden={showHighlights}>
		<!-- Keyed on entity identity (as are the geography and research-space sections below) so
		     navigating between entities tears the tree-driven components down and rebuilds them from
		     fresh props: FullQc and FlatOutFrame seed local state (tree spec, breakdowns, year) once from
		     prop defaults. The year filter mutates conf in place (same identity), so it stays within one
		     instance and hot-reloads through the tree loader. -->
		{#key entityKey}
			<FullQc
				rootName={data.view.name}
				prefixText={data.prefixText}
				selectedQcRootId={data.view.dmId}
				conf={data.conf}
				selectionState={data.selectionState}
				attributeLabels={data.atts}
				completeTree={data.tree}
				shallowed={data.shallowed}
				shoPathLevelInfo={!isHitPaper}
			/>
		{/key}
	</div>
</section>

{#if isAuthor && authoredHitPapers.length > 0}
	<section id="hits" class="shadowy padded marged main-block">
		<h2 id="papers">{data.view.name}'s Hit Papers</h2>
		<PaperRainbow papers={authoredHitPapers} {entityAtts} {discAuthorNames} />
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
		{#key entityKey}
			<WorldMapSvg
				rootId={data.view.dmId}
				{indsByEntityType}
				rootName={data.view.name}
				conf={data.conf}
			/>
		{/key}
	</section>
{/if}

{#if showsSubfields}
	<section id="research-space" class="shadowy padded marged main-block heighted">
		{#key entityKey}
			<ConceptMap
				rootId={data.view.dmId}
				{indsByEntityType}
				rootName={data.view.name}
				conf={data.conf}
			/>
		{/key}
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
			<AuthorLedgerPanel
				events={data.ledgerEvents}
				manifest={data.ledgerManifest}
				papers={$works.papers}
				semanticId={data.conf.semanticId}
				{ledger}
			/>
		{/if}

		<AllWorks
			{works}
			disownedWids={worksHidden.disownedWids}
			mergedPairs={worksHidden.mergedPairs}
			isOwner={data.isOwner}
			on:disown={handleDisown}
			on:undisown={handleUndisown}
			on:merge={handleMerge}
			on:unmerge={handleUnmerge}
		/>
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
				<RandTreeLink semanticId={sim.semanticId} name={sim.name} rootType={data.conf.rootType} />
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

	.impact-head {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		margin-bottom: 4px;
	}

	.impact-head h3 {
		margin: 0;
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
