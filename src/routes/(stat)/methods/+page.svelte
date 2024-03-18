<script lang="ts">
	import dStats from '$lib/assets/data/desc-stats.json';
	import oalexConcepts from '$lib/assets/data/concept-hier.json';

	import oaLogo from '$lib/assets/images/icons/openalex-logo.png';
	import scimagoLogo from '$lib/assets/images/icons/scimago-logo.png';
	import {formatNumber} from '$lib/text-format-util';

	import TileTreeMap from '$lib/components/TileTreeMap.svelte';
	import BrokenFittedText from '$lib/components/BrokenFittedText.svelte';
	import {onMount} from 'svelte';

	const dCards = [
		{desc: 'Works', num: dStats.counts.work, color: 15},
		{desc: 'Institutions', num: dStats.counts.inst, color: 25},
		{desc: 'Citations', num: dStats.counts.cite, color: 50},
		{desc: 'Countries', num: dStats.counts.country, color: 90}
	];

	let childNames = Object.values(oalexConcepts.children).map((e) => e.name);
	let childInd = 0;

	function updateGraph() {
		if (childInd == childNames.length * 4) {
			openChildren = [];
			expandedChild = undefined;
			explainBox = undefined;
			childInd = 0;
		} else {
			if (childInd % 4 == 0) {
				openChildren = [childNames[childInd / 4]];
				explainBox = Object.values(oalexConcepts.children).filter(
					(n) => n.name == openChildren[0]
				)[0];
			} else if (childInd % 4 == 1) {
				expandedChild = childNames[(childInd - 1) / 4];
			} else if (childInd % 4 == 2) {
				//expandedChild = childNames[(childInd - 1) / 4];
			} else {
				explainBox = undefined;
				expandedChild = undefined;
				openChildren = [];
			}
			childInd++;
		}
	}

	onMount(() => {
		setInterval(updateGraph, 3500);
	});

	let expandedChild: string | undefined = undefined;
	let openChildren: string[] = [];
	let explainBox: undefined | {cited_by_count: number; works_count: number; name: string} =
		undefined;
</script>

<div class="bstrip" id="card-block">
	{#each dCards as dCard}
	<div class="b-card" style="--cur: var(--color-range-{dCard.color});">
		{formatNumber(dCard.num)}
		{dCard.desc}
	</div>
	{/each}
</div>
<div class="bstrip">
	<p id="headline">
		We use <a href="#data">open, up-to-date data</a>, process it with
		<a href="#impact">transparent methods</a> and visualize the results in an
		<a href="#viz">intuitive, unique way</a>.
	</p>
</div>

<div class="bstrip">
	<svg id="concept-tiles" viewBox="0 -300 1000 1300">
		<g id="tmviz">
			<TileTreeMap data={oalexConcepts} maxPad={10} {openChildren} {expandedChild}
				transitionMs={1200} />
		</g>
		{#if explainBox != undefined}
		<BrokenFittedText text={explainBox.name} x={25} y={-10} width={500} height={140} />
		<BrokenFittedText text="{formatNumber(explainBox.cited_by_count, 0)} citations" x={650} y={-100}
			width={300} height={80} />
		<BrokenFittedText text="{formatNumber(explainBox.works_count, 0)} works" x={650} y={-10} width={300}
			height={80} />
		{/if}
	</svg>
</div>

<div class="bstrip">
	<div class="bar">
		<h2>FAQ</h2>
		<h4 id="data">What are your data-sources?</h4>
		<p>
			Primarily, the current <a
				href="https://docs.openalex.org/download-all-data/openalex-snapshot">OpenAlex
				snapshot</a>, but we extend it with journal classification and impact factor estimates
			from
			<a href="https://www.scimagojr.com/">Scimago</a>
		</p>
		<h4>How soon does a new paper make it into the data?</h4>
		<p>
			We aim to recalculate the complete dataset at least once a month, so as soon as a paper has
			been indexed by OpenAlex, it will appear in our database within a month.
		</p>
		<h4>Do you filter the data?</h4>
		<p>
			All works published after 2010 in Q1 or Q2 (classified at the time of publication by
			<a href="https://www.scimagojr.com/">Scimago</a>) are considered, with citations and author
			affiliations provided by OpenAlex. Institutions are filtered to those that have at least 1000
			such works and subsequently, only citations among these institutions are considered.
		</p>
		<h4>How do you classify papers and journals?</h4>
		<p>
			OpenAlex provides a hierarchy of <a
				href="https://docs.openalex.org/api-entities/concepts">concepts</a>
			and assigns them to each piece of work, based on the contents, while Scimago classifies journals
			into a hierarchy of 27 major thematic areas and 309 specific subject categories based on
			<a href="https://service.elsevier.com/app/answers/detail/a_id/15181/supporthub/scopus/">Scoups
				categorization</a>.
		</p>
		<h4 id="impact">How do you measure impact?</h4>
		<p>
			Our impact flows are based on citations, but in some cases we make use of coathorships to
			visualize relationships between institutions. In all cases, the number of citations are noted
			in the charts.
		</p>
		<h4 id="spec">What is specialization?</h4>
		<p>
			We use a modified version of the <a
				href="https://en.wikipedia.org/wiki/Revealed_comparative_advantage">Revealed comparative
				advantage</a> metric. To calculate RCA, we begin by selecting a meaningful reference
			group from the dataset.
			This reference group provides a baseline against which we evaluate the specialization of the
			entity
			in question. The RCA score is computed by comparing the proportion of an entity's impact in a
			specific
			field to the proportion of impact in the same field for the chosen reference group.
			Mathematically,
			RCA is expressed as: RCA = (Proportion of Entity's Impact in Field) / (Proportion of Reference
			Group's Impact in Field). We also introduce a correction term, so that branches that have very
			low expected impact don't dominate specialization.
		</p>
		<h4>
			What are the papers that actually make up the relationship between two institutiions in a
			certain field?
		</h4>
		<p>
			You can not see the actual list of papers at the moment that make up a branch of impact, but
			we are working on implementing it. Due to the nature of the data with hundreds of millions of
			citations, and our current architecture of statically serving everything, showing a concrete
			list of papers is challenging.
		</p>
		<h4>Do you weigh the impact of an institution based on number of authors?</h4>
		<p>
			Currently, no. All impact is measured tha same, even if one of 100 authors has an affiliation
			to an institution or 3 of 3. We plan to change this, or at least provide the option to view
			different ways but it is not straightforward to specify
		</p>
		<h4 id="viz">What kind of visualization engine do you use?</h4>
		<p>All our visualizations are hand-rolled SVGs with css transitions, made with svelte.</p>
	</div>
</div>
<div class="bstrip">
	<img src={oaLogo} alt="OpenAlex logo" />
	<img src={scimagoLogo} alt="Scimago logo" />
</div>

<style>
	p {
		text-align: justify;
	}

	#card-block {
		margin-top: 10svh;
		margin-bottom: 10svh;
	}

	#headline {
		font-size: 3rem;
		max-width: 1000px;
	}

	#headline>a {
		text-decoration: none;
		font-weight: 600;
		color: rgb(var(--color-range-25));
	}

	#concept-tiles {
		width: 90%;
		max-width: 900px;
	}

	.bar {
		justify-content: center;
		align-items: center;
		flex-wrap: wrap;
		flex: 0 1 600px;
		margin: 40px;
	}

	.bstrip>img {
		height: 100px;
		margin: 20px;
	}

	.b-card {
		font-weight: bold;
		padding: 30px;
		margin: 20px;
		/* border-radius: 30px; */
		background-color: rgba(var(--cur), 0.15);
		flex: 0 0 200px;
		/* border: 3px solid var(--cool-gray-20, #dde1e6); */
		box-shadow: 0px 4px 13px 0px rgba(0, 0, 0, 0.25);
	}
</style>
