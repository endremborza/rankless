<script lang="ts">
	import dStats from '$lib/assets/data/desc-stats.json';
	import oalexConcepts from '$lib/assets/data/concept-hier.json';

	import oaLogo from '$lib/assets/images/icons/openalex-logo.png';
	import scimagoLogo from '$lib/assets/images/icons/scimago-logo.png';
	import {formatNumber} from '$lib/text-format-util';

	import TileTreeMap from '$lib/components/TileTreeMap.svelte';
	import BrokenFittedText from '$lib/components/BrokenFittedText.svelte';
	import {onMount} from 'svelte';
	import AccordionElement from '$lib/components/AccordionElement.svelte';

	type TextAtt = {x: number; y: number; width: number; height: number};

	let innerWidth: number;
	let viewBox: string;
	let subjectTextAtts: TextAtt;
	let subjectNumAtts: TextAtt;
	let selectedId: string | undefined = undefined;

	function pickId(id: string) {
		return () => {
			selectedId = id;
		};
	}

	function getSvgShape(width: number) {
		viewBox = '-300 0 1600 1000';
		subjectTextAtts = {x: -250, y: 500, width: 230, height: 140};
		subjectNumAtts = {x: 1020, y: 450, width: 230, height: 80};
		if (width < 1200) {
			viewBox = '0 -200 1000 1200';
			subjectTextAtts = {x: 25, y: -10, width: 500, height: 140};
			subjectNumAtts = {x: 650, y: -100, width: 300, height: 80};
		}
	}

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

	$: getSvgShape(innerWidth);
	$: lowerNumAtts = {...subjectNumAtts, y: subjectNumAtts.y + 90};
</script>

<svelte:window bind:innerWidth />

<div class="bstrip" id="card-block">
	{#each dCards as dCard}
	<div class="b-card">
		<div class="card-text">
			<div>
				{formatNumber(dCard.num)}
			</div>
			<div class="card-desc">
				{dCard.desc}
			</div>
		</div>
		<div class="card-box" style="background-color: rgba(var(--color-range-{dCard.color}), 0.6);" />
	</div>
	{/each}
</div>
<div class="bstrip">
	<p id="headline">
		We use <a on:click={pickId('data')} href="#data">open, up-to-date data</a>, process it with
		<a on:click={pickId('impact')} href="#impact">transparent methods</a> and visualize the results
		in an
		<a on:click={pickId('viz')} href="#viz">intuitive, unique way</a>.
	</p>
</div>

<div class="bstrip" id="tile-strip">
	<svg id="concept-tiles" {viewBox}>
		<g id="tmviz">
			<TileTreeMap data={oalexConcepts} maxPad={10} {openChildren} {expandedChild}
				transitionMs={1200} />
		</g>
		{#if explainBox != undefined}
		<BrokenFittedText text={explainBox.name} {...subjectTextAtts} />
		<BrokenFittedText text="{formatNumber(explainBox.cited_by_count, 0)} citations" {...subjectNumAtts} />
		<BrokenFittedText text="{formatNumber(explainBox.works_count, 0)} works" {...lowerNumAtts} />
		{/if}
	</svg>
</div>

<div class="bstrip">
	<div class="bar">
		<!-- TODO: fix numbers -->
		<!-- TODO: explain the data -->
		<!-- TODO: timeframe related thing -->
		<div id="faq-head">
			<h1>FAQ</h1>
			<p id="faq-p">
				Questions and answers about data sources used, update frequency, filtering, impact
				measurement, extensions and visualization.
			</p>
		</div>
		<div id="faq-acc">
			<AccordionElement bind:selectedId title="What are your data-sources?" id="data">
				Primarily, the current <a
					href="https://docs.openalex.org/download-all-data/openalex-snapshot">OpenAlex
					snapshot</a>, but we extend it with journal classification and impact factor
				estimates from
				<a href="https://www.scimagojr.com/">Scimago</a>
			</AccordionElement>

			<AccordionElement bind:selectedId title="Can I get an export of your data?" id="q-2">
				Our data is derived from our <a href="data">sources</a> in a way that makes it efficient
				to digest
				for our visualization engine, so it is not necessarily simple to use ad-hoc analysis.
				Everything
				we show can be derived from the combination of OpenAley snapshot and Scimago.
			</AccordionElement>

			<AccordionElement bind:selectedId title="How frequently do you update the data?" id="q-3">
				We aim to recalculate the complete dataset at least once a month.
			</AccordionElement>

			<AccordionElement bind:selectedId
				title="How do you ensure the accuracy and reliability of the data presented?" id="q-4">
				We don't, OpenAlex does.
			</AccordionElement>

			<AccordionElement bind:selectedId title="
				Can users provide feedback or suggest improvements to your dataset? If so, how can they do
				that?
			" id="q-5">
				Write to Vera: veronika.hamar@uni-corvinus.hu
			</AccordionElement>

			<AccordionElement bind:selectedId title="
				Do you have plans to incorporate additional data sources or expand the scope of your dataset
				in the future?
			" id="q-6">
				The two main immediate expansion are showing data on the paper level and utilizing
				information about individual authors. To properly utilize the individual level
				information,
				the solution to <a
					href="https://docs.openalex.org/api-entities/authors/author-disambiguation">the
					disambiguation problem</a> will need to be improved and investigated.
			</AccordionElement>

			<AccordionElement bind:selectedId title="How soon does a new paper make it into the data?"
				id="q-7">
				We are targeting monthly updates, so as soon as a paper has been indexed by OpenAlex, it
				will appear in our database within a month.
			</AccordionElement>

			<AccordionElement bind:selectedId title="Do you filter the data?" id="q-8">
				All works published after 2010 in Q1 or Q2 (classified at the time of publication by <a
					href="https://www.scimagojr.com/">Scimago</a>) are considered, with citations
				and author affiliations provided by OpenAlex. Institutions
				are filtered to those that have at least 1000 such works and subsequently, only
				citations
				among these institutions are considered.
			</AccordionElement>

			<AccordionElement bind:selectedId title="How do you classify papers and journals?" id="q-9">
				OpenAlex provides a hierarchy of <a
					href="https://docs.openalex.org/api-entities/concepts">concepts</a>
				and assigns them to each piece of work, based on the contents, while Scimago classifies
				journals
				into a hierarchy of 27 major thematic areas and 309 specific subject categories based on
				<a href="https://service.elsevier.com/app/answers/detail/a_id/15181/supporthub/scopus/">Scoups
					categorization</a>.
			</AccordionElement>

			<AccordionElement bind:selectedId title="How do you measure impact?" id="impact">
				Our impact flows are based on citations, but in some cases we make use of coathorships
				to
				visualize relationships between institutions. In all cases, the number of citations are
				noted in the charts.
			</AccordionElement>

			<AccordionElement bind:selectedId title="What is specialization?" id="spec">
				We use a modified version of the <a
					href="https://en.wikipedia.org/wiki/Revealed_comparative_advantage">Revealed
					comparative advantage</a> metric. To calculate RCA, we begin by selecting a
				meaningful reference group from the dataset.
				This reference group provides a baseline against which we evaluate the specialization of
				the
				entity in question. The RCA score is computed by comparing the proportion of an entity's
				impact
				in a specific field to the proportion of impact in the same field for the chosen
				reference group.
				Mathematically, RCA is expressed as: RCA = (Proportion of Entity's Impact in Field) /
				(Proportion
				of Reference Group's Impact in Field). We also introduce a correction term, so that
				branches
				that have very low expected impact don't dominate specialization.
			</AccordionElement>

			<AccordionElement bind:selectedId title="
				What are the papers that actually make up the relationship between two institutiions in a
				certain field?
			" id="q-12">
				You can not see the actual list of papers at the moment that make up a branch of impact,
				but
				we are working on implementing it. Due to the nature of the data with hundreds of
				millions
				of citations, and our current architecture of statically serving everything, showing a
				concrete list of papers is challenging.
			</AccordionElement>

			<AccordionElement bind:selectedId
				title="Do you weigh the impact of an institution based on number of authors?" id="q-13">
				Currently, no. All impact is measured tha same, even if one of 100 authors has an
				affiliation to an institution or 3 of 3. We plan to change this, or at least provide the
				option to view different ways but it is not straightforward to specify
			</AccordionElement>

			<AccordionElement bind:selectedId title="What kind of visualization engine do you use?"
				id="viz">
				All our visualizations are hand-rolled SVGs with css transitions, made with svelte.
			</AccordionElement>
		</div>
	</div>
</div>
<div class="bstrip logo-strip">
	<img src={oaLogo} style="width: 265.5px;" class="logo" alt="OpenAlex logo" />
	<img src={scimagoLogo} style="width: 140px;" class="logo" alt="Scimago logo" />
</div>

<style>
	p {
		text-align: justify;
	}

	h1 {
		font-size: 3.5rem;
	}

	#card-block {
		margin-top: 70px;
		margin-bottom: 40px;
	}

	#headline {
		font-size: min(3rem, 5vw);
		max-width: 1000px;
		margin-right: 30px;
		margin-left: 30px;
	}

	#headline>a {
		text-decoration: none;
		font-weight: 600;
		color: rgb(var(--color-range-25));
	}

	#tile-strip {
		padding-top: 80px;
		padding-bottom: 80px;
		background-color: var(--color-theme-lightblue);
	}

	#concept-tiles {
		height: 800px;
		max-height: min(80svh, 110vw);
		width: 100%;
	}

	#faq-head {
		width: 600px;
		max-width: 90vw;
	}

	#faq-acc {
		width: 1000px;
		max-width: 90vw;
	}

	#faq-p {
		padding-right: 15px;
		text-align: left;
		max-width: 400px;
	}

	.bar {
		display: flex;
		justify-content: space-around;
		align-items: start;
		flex-wrap: wrap;
		margin: 40px;
	}

	.b-card {
		display: flex;
		justify-content: end;
		font-weight: bold;
		padding: 30px;
		padding-top: 18px;
		padding-bottom: 18px;
		margin: 20px;
		flex: 0 0 200px;
		box-shadow: 0px 4px 13px 0px rgba(0, 0, 0, 0.25);
	}

	.card-text {
		text-align: right;
		font-size: 18px;
	}

	.card-desc {
		font-weight: 300;
	}

	.card-box {
		width: 44px;
		height: 44px;
		margin-left: 20px;
		opacity: 75%;
	}
</style>
