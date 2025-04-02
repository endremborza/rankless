<script lang="ts">
	import { APP_NAME } from '$lib/constants';
	import { prettifyRoot } from '$lib/text-format-util';

	import type * as tt from '$lib/tree-types';

	import FullQc from '$lib/components/FullQc.svelte';
	import YearTicks from '$lib/components/YearTicks.svelte';
	import RandTreeLink from '$lib/components/RandTreeLink.svelte';
	import HoverI from '$lib/components/HoverI.svelte';
	import HoverBlock from '$lib/components/HoverBlock.svelte';
	import Webby from '$lib/components/Webby.svelte';

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
</script>

<svelte:head>
	<title>{data.view.name} - scholarly publications and citations - {APP_NAME}</title>
	<meta name="description" content={data.metaDescriptions} />
	<meta property="og:image" content={data.svgLink} />
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
				<span><a href="/about#indexed-citation" target="blank_">{data.citeText}</a></span>
				<HoverI bind:hoverToggle={showIndexedCiteText} />.
			</div>
		</div>
		<div id="about">
			<h3>About</h3>
			<div>
				{data.aboutParagraph.prefix}.
				{@html data.aboutParagraph.postText}
			</div>
		</div>
	</div>
	<div id="era">
		<h3>In The Last Decade</h3>
		<div bind:clientHeight={ticksHeight}>
			<YearTicks
				bottomStacks={data.view.yearlyPapers}
				topStacks={data.view.yearlyCites}
				fullHeight={ticksHeight}
			/>
		</div>
	</div>
</div>
<div id="tree-row" class="shadowy padded marged">
	<div bind:clientWidth={innerWidth} bind:clientHeight={innerHeight} id="tree">
		<FullQc
			rootName={data.view.name}
			selectedQcRootId={data.view.dmId}
			conf={data.conf}
			prefixText={data.prefixText}
			selectionState={data.selectionState}
			treeSpecs={data.treeSpecs}
			removeHighlightUnhover={false}
			attributeLabels={data.atts}
			completeTree={data.tree}
			{innerHeight}
			{innerWidth}
			shallowed={data.shallowed}
		/>
	</div>
</div>
<div class="shadowy padded marged">
	<Webby />
</div>
<div id="similars" class="shadowy padded marged">
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
		height: 100svh;
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
</style>
