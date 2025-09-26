<script lang="ts">
	import {APP_NAME, REL_TYPES} from '$lib/constants';
	import {prettifyRoot} from '$lib/text-format-util';

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
	// import PaperRainbow from '$lib/components/PaperRainbow.svelte';

	let innerHeight: number;
	let innerWidth: number;

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
		let names = [];
		let scores = [];
		for (const rel of view.primeRelations) {
			if (REL_TYPES[rel.relType] == 'paper-authors') {
				names.push(rel.name);
				scores.push(rel.score);
			}
		}
		return {names, scores};
	}

	//resp might remain 0, so we need to alert the country map
	$: indsByEntityType = tf.getTreeIndsByEntityType(data.treeSpecs.specs[data.conf.rootType]);
	$: showsCountry = indsByEntityType.countries.length > 0;
	$: showsSubfields = indsByEntityType.subfields.length > 0;
	let showAuthorNetwork = true;
	$: authorStats = getAuthorStats(data.view);
	$: topAuthorNames = authorStats.names;
	$: authorNumbers = authorStats.scores;
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
		<HoverBlock show={showIndexedCiteText} style={'top: 20svh; left:20vw; width: 60vw;max-width: 550px'}>
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
			<YearTicks bottomStacks={data.view.yearlyPapers} topStacks={data.view.yearlyCites}
				fullHeight={ticksHeight} />
		</div>
	</div>
</div>
<div class="comp-basis">
	{#if showAuthorNetwork}
	<div class="shadowy padded marged" id="author-network">
		<AuthorNetwork nodes={topAuthorNames} edgeWeights={data.view.authorNetwork}
			nodeIntensities={authorNumbers} />
	</div>
	{/if}
	<div class="shadowy padded marged">
		<div bind:clientWidth={innerWidth} bind:clientHeight={innerHeight} id="tree">
			<FullQc rootName={data.view.name} prefixText={data.prefixText} selectedQcRootId={data.view.dmId}
				conf={data.conf} selectionState={data.selectionState} treeSpecs={data.treeSpecs}
				removeHighlightUnhover={false} attributeLabels={data.atts} completeTree={data.tree}
				{innerHeight} {innerWidth} shallowed={data.shallowed} />
		</div>
	</div>
	{#if showsSubfields}
	<div class="shadowy padded marged" id="research-space">
		<ConceptMap rootId={data.view.dmId} {indsByEntityType} rootName={data.view.name} conf={data.conf}
			treeSpecs={data.treeSpecs} />
	</div>
	{/if}
	{#if showsCountry}
	<div class="shadowy padded marged" id="world-map">
		<WorldMapSvg rootId={data.view.dmId} {indsByEntityType} rootName={data.view.name} conf={data.conf}
			treeSpecs={data.treeSpecs} />
	</div>
	{/if}
</div>
<!-- <div class="shadowy padded marged"> -->
<!-- 	<PaperRainbow papers={data.view.hitPapers} /> -->
<!-- </div> -->
<div id="similars" class="shadowy padded marged">
	<h3>Explore {prettifyRoot(data.conf.rootType)} with similar magnitude of impact</h3>
	<div>
		{#each data.view.similars as sim}
		<span>
			<RandTreeLink semanticId={sim.semanticId} name={sim.name} rootType={data.conf.rootType}
				treeSpecs={data.treeSpecs} />
		</span>
		{/each}
	</div>
</div>

<style>
	@media (max-width: 800px) {
		#era>div {
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

	#name-block {
		flex: 8;
	}

	#era {
		flex: 4;
	}

	#era>div {
		aspect-ratio: 2.5;
	}

	#tree {
		height: 100svh;
	}

	#similars {
		margin-bottom: 40px;
	}

	#similars>div {
		width: 100%;
		padding-top: 28px;
		padding-bottom: 48px;
		display: flex;
		flex-wrap: wrap;
		justify-content: space-evenly;
		align-items: stretch;
		gap: 40px;
	}

	#similars>div>span {
		min-width: 180px;
		flex: 1 0 21%;
		padding: 6px;
		border-bottom: solid var(--color-theme-blue) 3px;
		background: rgba(var(--color-range-15), 0.1);
	}

	#world-map {
		display: flex;
		flex-direction: column;
		justify-content: center;
		height: 100%;
	}
</style>
