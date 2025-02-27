<script lang="ts">
	import { APP_NAME, COMPLETE_YEAR } from '$lib/constants';
	import { pluralize, prettifyRoot, SEMANTIC_CONF, semantify } from '$lib/text-format-util';
	import { entToLink, getDefaultYear, idFromBd, toLinkWithParams } from '$lib/tree-functions';

	import type * as tt from '$lib/tree-types';

	import FullQc from '$lib/components/FullQc.svelte';
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

	const REL_DESCS = [
		'Papers in fields',
		'Citing in fields',
		'Papers in topics',
		'Collaborations with nation',
		'Published in journal'
	];

	function getTopRels(view: tt.View) {
		const out = [];
		let id = 0;
		let sub: { desc: string; subs: tt.RelatedEntity[] } = { desc: REL_DESCS[id], subs: [] };
		for (const rel of view.primeRelations) {
			if (rel.relType != id) {
				out.push(sub);
				id = rel.relType;
				sub = { desc: REL_DESCS[id], subs: [] };
			}
			sub.subs.push(rel);
		}
		out.push(sub);

		return out;
	}

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
	$: topRels = getTopRels(data.view);

	$: decadePTxt = data.view.yearlyPapers.reduce((l, r) => r + l);
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
				and
				<span><a href="/about#indexed-citation" target="blank_">{citeText}</a></span>
			</div>
		</div>
		<div id="about">
			<h3>About</h3>
			<div>
				{#if rootType == 'authors'}
					{rootName} has authored {paperText} that have received a total of {citeText}. During the
					last decade {rootName} has published {decadePTxt} papers.
				{:else if rootType == 'institutions'}
					Since {COMPLETE_YEAR} authors affiliated with {rootName} have published {paperText}, which
					have received a total of {citeText}.
				{:else if rootType == 'subfields'}
					{paperText}
				{:else if rootType == 'countries'}
					Since {COMPLETE_YEAR} scholars affiliated with institutions in {rootName} have published
					{paperText}, which have received a total of {citeText}.
				{:else if rootType == 'sources'}
					{paperText}
				{/if}
				<ul>
					{#each topRels as rel}
						<li><b>{rel.desc}</b></li>
						<ul>
							{#each rel.subs as sub}
								<li>{sub.name} {sub.score}</li>
							{/each}
						</ul>
					{/each}
				</ul>
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
		gap: 40px;
	}

	#name-block {
		display: flex;
		flex: 8;
		flex-wrap: wrap;
		flex-direction: column;
		justify-content: space-between;
		align-items: top;
	}

	#nametag {
		min-width: 300px;
	}

	#era {
		flex: 4;
		padding: 0px;
		display: flex;
		flex-direction: column;
		justify-content: space-between;
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
		flex: 1 0 21%;
		padding: 6px;
		border-bottom: solid var(--color-theme-blue) 3px;
		background: rgba(var(--color-range-15), 0.1);
	}
</style>
