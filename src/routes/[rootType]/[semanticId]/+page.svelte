<script lang="ts">
	import { APP_NAME, LATEST_YEAR } from '$lib/constants';
	import { pluralize, prettifyRoot, SEMANTIC_CONF, semantify } from '$lib/text-format-util';
	import { entToLink, getDefaultYear, idFromBd, toLinkWithParams } from '$lib/tree-functions';

	import type * as tt from '$lib/tree-types';

	import FullQc from '$lib/components/FullQc.svelte';
	import { getColor } from '$lib/style-util';
	import TimelineViz from '$lib/components/TimelineViz.svelte';
	import YearTicks from '$lib/components/YearTicks.svelte';
	import RandTreeLink from '$lib/components/RandTreeLink.svelte';

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
	};
	let hoveredName = '';
	$: treeSpecs = data.treeSpecs;
	$: rootType = data.conf.rootType;
	$: citeCount = data.view.citations;
	$: paperCount = data.view.papers;
	$: rootName = data.view.name;
	$: selectedQcRootId = data.view.dmId;
	$: titleExtension = rootName.length > 0 ? ` - ${rootName}` : '';
	$: prefixText = SEMANTIC_CONF[rootType]?.start || '';
	$: paperText = pluralize('paper', paperCount);
	$: citeText = pluralize('indexed citation', citeCount);
	$: metaDescriptions = `Breaking down the impact of ${prefixText.toLowerCase()} ${rootName} - ( ${paperText}, ${citeText} )`;

	let relInstTitle = 'Affiliation History';

	const lineWidth = 80;

	function semantifySfCoords(coords: [number, number]) {
		let [refC, citC] = coords;
		let refSem =
			'are neither overly focused on a small set of topics, neither heavily multidisciplinary';
		let citSem = 'come from a range of fields that is about as wide as to be expected';
		if (refC < -0.7) {
			refSem = 'cover a broader set of topics than expected';
		} else if (refC > 0.7) {
			refSem = 'are more focused on a single topic than usual';
		}
		if (citC < 0.7) {
			citSem = 'branch out to more disciplines than usual';
		} else if (citC > 0.7) {
			citSem = 'are generally from the same field of study';
		}
		return [refSem, citSem];
	}

	function getTopSems(treeSpecs: tt.TreeSpecs, rootType: tt.RootType): string[] {
		let tops = [];
		for (const tSpec of treeSpecs.specs[rootType]) {
			let entry = semantify(idFromBd(tSpec.breakdowns[0]), rootType, [], 0);
			if (tops.indexOf(entry) == -1) {
				tops.push(entry);
			}
		}
		return tops;
	}

	function getDecatePapers(view: tt.View) {
		const dN = view.yearlyPapers.reduce((l, r) => r + l);
		return dN;
	}

	$: decadePTxt = getDecatePapers(data.view);
	$: semTops = getTopSems(treeSpecs, rootType);

	$: [refSideSem, citSideSem] = semantifySfCoords(data.view.sfCoords);
	let bdtName = 'Breakdown Trees';
</script>

<svelte:head>
	<title>{APP_NAME}{titleExtension}</title>
	<meta name="description" content={metaDescriptions} />
	<meta property="og:image" content={data.svgLink} />
</svelte:head>

<div id="head-row" class="shadowy padded marged">
	<div id="name-block">
		<div id="nametag">
			<h1>{rootName}</h1>
			<div>
				<span>{paperText}</span>
				<span>{citeText}</span>
			</div>
		</div>
		<div id="about">
			<h3>About</h3>
			<div>
				{#if rootType == 'authors'}
					{rootName} has authored {paperText}, with {citeText}, {decadePTxt} of these were published
					in the last decade. These papers
					{refSideSem}, while the papers citing them {citSideSem}.
				{:else if rootType == 'institutions'}
					{paperText} published by authors affiliated with {rootName}, with {citeText}
				{:else if rootType == 'subfields'}
					{paperText}
				{:else if rootType == 'countries'}
					{paperText}
				{:else if rootType == 'sources'}
					{paperText}
				{/if}
				Explore these papers and their impact in more detail in our <a href="#tree">{bdtName}</a>.
			</div>
		</div>
	</div>
	<div id="era">
		<h3>In The Last Decade</h3>
		<div>
			<YearTicks bottomStacks={data.view.yearlyPapers} topStacks={data.view.yearlyCites} />
		</div>
	</div>
</div>
<div id="tree-row" class="shadowy padded marged">
	<div bind:clientWidth={innerWidth} bind:clientHeight={innerHeight} id="tree">
		<FullQc
			{rootName}
			{selectedQcRootId}
			conf={data.conf}
			{prefixText}
			selectionState={data.selectionState}
			{treeSpecs}
			removeHighlightUnhover={false}
			attributeLabels={data.atts}
			completeTree={data.tree}
			{innerHeight}
			{innerWidth}
		/>
	</div>
</div>
<div id="similars" class="shadowy padded marged">
	<h3>Explore {prettifyRoot(rootType)} with similar magnitude of impact</h3>
	<div>
		{#each data.view.similars as sim}
			<span>
				<RandTreeLink semanticId={sim.semanticId} name={sim.name} {rootType} {treeSpecs} />
			</span>
		{/each}
	</div>
</div>

<style>
	#head-row {
		display: flex;
		flex-wrap: wrap;
		min-height: 180px;
		align-items: stretch;
		/* border: solid var(--color-theme-pink) 3px; */
	}

	#name-block {
		display: flex;
		flex: 7;
		flex-wrap: wrap;
		flex-direction: column;
		justify-content: space-between;
		align-items: top;
	}

	#nametag {
		min-width: 300px;
	}

	#era {
		flex: 5;
		padding: 0px;
		/* border: solid black 1px; */
	}

	#era > div {
		aspect-ratio: 2.5;
		min-width: 300px;
	}

	#about {
		min-width: 300px;
	}

	#tree-row {
		height: 100svh;
	}

	#tree {
		height: 100%;
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
		/* max-width: 240px; */
		flex: 1 0 21%;
		padding: 6px;
		border-bottom: solid var(--color-theme-blue) 3px;
		background: rgba(var(--color-range-15), 0.1);
	}
</style>
