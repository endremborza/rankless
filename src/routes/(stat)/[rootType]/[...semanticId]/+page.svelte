<script lang="ts">
	import { APP_NAME, REL_TYPES } from '$lib/constants';
	import { prettifyRoot } from '$lib/text-format-util';

	import type * as tt from '$lib/tree-types';
	import * as tf from '$lib/tree-functions';

	import FullQc from '$lib/components/FullQc.svelte';
	import YearTicks from '$lib/components/YearTicks.svelte';
	import RandTreeLink from '$lib/components/RandTreeLink.svelte';
	import HoverI from '$lib/components/HoverI.svelte';
	import HoverBlock from '$lib/components/HoverBlock.svelte';
	import WorldMapSvg from '$lib/components/WorldMapSvg.svelte';
	import ConceptMap from '$lib/components/ConceptMap.svelte';
	import AuthorNetwork from '$lib/components/AuthorNetwork.svelte';
	import PaperRainbow from '$lib/components/PaperRainbow.svelte';

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
	};

	let showIndexedCiteText = false;
	let ticksHeight: number;

	function getAuthorStats(view: tt.View) {
		let authorNames = [];
		let authorScores = [];

		for (const rel of view.primeRelations) {
			if (REL_TYPES[rel.relType] == 'paper-authors') {
				authorNames.push(rel.name);
				authorScores.push(rel.score);
			}
		}
		return { authorNames, authorScores, edgeWeights: view.authorNetwork };
	}

	//resp might remain 0, so we need to alert the country map
	$: indsByEntityType = tf.getTreeIndsByEntityType(data.treeSpecs.specs[data.conf.rootType]);
	$: showsCountry = indsByEntityType.countries.length > 0;
	$: showsSubfields = indsByEntityType.subfields.length > 0;
	$: showAuthorNetwork = data.conf.rootType == 'authors';
	$: authorStats = getAuthorStats(data.view);
</script>

<svelte:head>
	<title>{APP_NAME} | {data.view.name}</title>
	<meta name="twitter:card" content="summary" />
	<meta name="twitter:creator" content="@LearningCCL" />
	<meta name="description" content={data.metaDescriptions} />
	<meta property="og:image" content={data.svgLink} />
	<meta property="og:title" content="{data.view.name} | {APP_NAME}" />
	<link rel="canonical" href={tf.externalEntityUrl(data.conf.rootType, data.conf.semanticId)} />
</svelte:head>

<div id="head-row" class="shadowy padded marged">
	<div id="name-block">
		<HoverBlock
			show={showIndexedCiteText}
			style={'top: 20svh; left:20vw; width: 60vw;max-width: 550px'}
		>
			Citations made by non-retracted papers categorized as "article", "book", or "review" that have
			received at least one citation.
		</HoverBlock>
		<div id="nametag">
			<h1>{data.view.name}</h1>
			<div>
				<span>{data.paperText}</span>
				and
				<span><a href="/#indexed-citation" target="blank_">{data.citeText}</a></span>
				<HoverI bind:hoverToggle={showIndexedCiteText} />.
			</div>
		</div>
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
			/>
		</div>
	</div>
</div>
<div class="comp-basis">
	{#if showAuthorNetwork}
		<div class="shadowy padded marged heighted" id="author-network">
			<AuthorNetwork
				nodes={authorStats.authorNames}
				edgeWeights={authorStats.edgeWeights}
				nodeIntensities={authorStats.authorScores}
				rootName={data.view.name}
			/>
		</div>
	{/if}
	<div class="shadowy padded marged" id="tree">
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
		/>
	</div>
	{#if showsSubfields}
		<div class="shadowy padded marged heighted" id="research-space">
			<ConceptMap
				rootId={data.view.dmId}
				{indsByEntityType}
				rootName={data.view.name}
				conf={data.conf}
				treeSpecs={data.treeSpecs}
			/>
		</div>
	{/if}
	{#if showsCountry}
		<div class="shadowy padded marged heighted" id="world-map">
			<WorldMapSvg
				rootId={data.view.dmId}
				{indsByEntityType}
				rootName={data.view.name}
				conf={data.conf}
				treeSpecs={data.treeSpecs}
			/>
		</div>
	{/if}
</div>
{#if data.conf.rootType === 'authors'}
	<a href="/author-papers/{data.conf.semanticId}" class="explore-card shadowy padded marged">
		<div>
			<h3>Top Papers & Citation Paths</h3>
			<p>
				Explore {data.view.name}'s most cited publications and discover how their work connects
				to other scholars through citations.
			</p>
		</div>
		<span class="explore-arrow">&#8594;</span>
	</a>
{:else if data.view.hitPapers.length > 0}
	<div class="shadowy padded marged">
		<PaperRainbow papers={data.view.hitPapers} />
	</div>
{/if}
<div id="similars" class="shadowy padded marged">
	<p>
		Rankless uses publication and citation data sourced from OpenAlex, an open and comprehensive
		bibliographic database. While OpenAlex provides broad and valuable coverage of the global
		research landscape, it—like all bibliographic datasets—has inherent limitations. These include
		incomplete records, variations in author disambiguation, differences in journal indexing, and
		delays in data updates. As a result, some metrics and network relationships displayed in
		Rankless may not fully capture the entirety of a scholar’s output or impact.
	</p>
	{#if data.aboutParagraph.footText.length > 0}<p>{@html data.aboutParagraph.footText}</p> {/if}
	<h3>Explore {prettifyRoot(data.conf.rootType)} with similar magnitude of impact</h3>
	<div>
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
</div>

<style>
	.comp-basis {
		display: grid;
		grid-template-columns: 1fr;
	}

	.heighted {
		display: flex;
		justify-content: space-between;
		align-items: center;
		flex-wrap: wrap;
	}

	@media (min-aspect-ratio: 3 / 1) and (min-height: 1200px) {
		.comp-basis:has(#author-network):has(#research-space) {
			grid-template-columns: 1fr 1fr;
		}

		.comp-basis:has(#author-network):has(#research-space) #author-network {
			grid-column: 1;
			grid-row: 1;
		}

		.comp-basis:has(#author-network):has(#research-space) #research-space {
			grid-column: 2;
			grid-row: 1;
		}
	}

	@media (max-width: 800px) {
		#era > div {
			width: 100%;
		}
	}

	@media (min-width: 801px) {
		#head-row {
			display: flex;
			flex-wrap: wrap;
			align-items: stretch;
			gap: 40px;
		}
	}

	#head-row {
		margin-top: var(--unified-margin);
	}

	#name-block {
		flex: 8;
	}

	#era {
		flex: 4;
	}

	#era > div {
		aspect-ratio: 2.5;
	}

	#tree {
		grid-column: 1 / -1;
	}

	#world-map {
		grid-column: 1 / -1;
		display: flex;
		flex-direction: column;
		justify-content: center;
	}

	#similars {
		margin-bottom: 40px;
	}

	#similars > div {
		width: 100%;
		padding-top: 28px;
		padding-bottom: 48px;
		display: flex;
		flex-wrap: wrap;
		justify-content: space-evenly;
		align-items: stretch;
		gap: 40px;
	}

	#similars > div > span {
		min-width: 180px;
		flex: 1 0 21%;
		padding: 6px;
		border-bottom: solid var(--color-theme-blue) 3px;
		background: rgba(var(--color-range-15), 0.1);
	}

	.explore-card {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 24px;
		text-decoration: none;
		color: var(--color-text);
		border-left: 4px solid var(--color-theme-blue);
		transition: border-color 0.2s, background-color 0.2s;
	}

	.explore-card:hover {
		border-left-color: var(--color-theme-yellow);
		background-color: rgba(var(--color-range-15), 0.06);
	}

	.explore-card h3 {
		margin: 0 0 6px;
	}

	.explore-card p {
		margin: 0;
		opacity: 0.7;
		font-size: 0.9rem;
	}

	.explore-arrow {
		font-size: 1.8rem;
		opacity: 0.4;
		flex-shrink: 0;
		transition: opacity 0.2s, transform 0.2s;
	}

	.explore-card:hover .explore-arrow {
		opacity: 0.8;
		transform: translateX(4px);
	}
</style>
