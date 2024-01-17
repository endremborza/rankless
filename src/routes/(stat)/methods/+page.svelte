<script lang="ts">
	import dStats from '$lib/assets/data/desc-stats.json';

	import oaLogo from '$lib/assets/images/icons/openalex-logo.png';
	import scimagoLogo from '$lib/assets/images/icons/scimago-logo.png';
	import { formatNumber } from '$lib/text-format-util';

	import oalexConcepts from '$lib/assets/data/concept-hier.json';
	import TileTreeMap from '$lib/components/TileTreeMap.svelte';

	const dCards = [
		{ desc: 'Works', num: dStats.counts.work, color: 15 },
		{ desc: 'Institutions', num: dStats.counts.inst, color: 25 },
		{ desc: 'Citations', num: dStats.counts.cite, color: 50 },
		{ desc: 'Countries', num: dStats.counts.country, color: 90 }
	];
</script>

<div class="bstrip">
	<div class="bar">
		<h1>We use a large, open, up-to-date dataset.</h1>
		<div class="logos">
			<img src={oaLogo} alt="OpenAlex logo" />
			<img src={scimagoLogo} alt="Scimago logo" />
		</div>
	</div>

	<div class="bar">
		<p>
			A daily-updated snapshot of <a href="https://openalex.org/">OpenAlex</a>, a complex, open
			catalog of scholarly works is processed in a transparent way, to create our profiles and
			visualizations. Currently, <b style="color: red; font-size:larger">TODO this might change!</b>
			all works published after 2010 in Q1 or Q2 (classified at the time of publication by
			<a href="https://www.scimagojr.com/">Scimago</a>) are considered, with citations and author
			affiliations provided by OpenAlex. Institutions are filtered to those that have at least 1000
			such works and subsequently, only citations among these institutions are considered.
		</p>
	</div>
</div>

<div class="bstrip">
	{#each dCards as dCard}
		<div class="b-card" style="--cur: var(--color-range-{dCard.color});">
			{formatNumber(dCard.num)}
			{dCard.desc}
		</div>
	{/each}
</div>

<div class="bstrip">
	<div class="bar">
		<p>
			OpenAlex provides a hierarchy of <a href="https://docs.openalex.org/api-entities/concepts"
				>concepts</a
			>
			and assigns them to each piece of work, based on the contents, while Scimago classifies journals
			into a hierarchy of 27 major thematic areas and 309 specific subject categories based on
			<a href="https://service.elsevier.com/app/answers/detail/a_id/15181/supporthub/scopus/"
				>Scoups categorization</a
			>. These hierarchies of concepts and journal classifications serve as the foundation for our
			analysis. They allow us to define fields of study, ensuring that one can evaluate entities
			within their relevant academic contexts. By leveraging these openly available resources, we're
			able to offer users a comprehensive, data-driven exploration of academic impact,
			specialization, and expertise across diverse fields and subject categories.
		</p>

		<p>
			The <a href="https://en.wikipedia.org/wiki/Revealed_comparative_advantage"
				>Revealed comparative advantage</a
			> metric allows us to assess the relative specialization or expertise of various entities within
			the academic landscape. To calculate RCA, we begin by selecting a meaningful reference group from
			dataset. This reference group provides a baseline against which we evaluate the specialization
			of the entity in question. The RCA score is computed by comparing the proportion of an entity's
			impact in a specific field to the proportion of impact in the same field for the chosen reference
			group. Mathematically, RCA is expressed as: RCA = (Proportion of Entity's Impact in Field) / (Proportion
			of Reference Group's Impact in Field)
		</p>

		<p>
			It's important to note that the choice of impact definition and reference group can vary
			depending on the specific analysis goals and context. In some cases, we might measure impact
			in terms of the number of papers published, whereas in others, we may use the number of
			citations received. Additionally, the reference group itself can be tailored to the specific
			question at hand. For example, when assessing the impact of a research entity within a on a
			specific university, the reference group may consist exclusively of entities from that same
			country, providing a localized context for the analysis.
		</p>
	</div>

	<div class="bar">
		<h1>We utilize predefined classification, and calculate simple metrics.</h1>
		<div class="tile-container">
			<svg height="100%" width="100%" viewBox="0 0 1000 1000">
				<TileTreeMap data={oalexConcepts} maxPad={10} />
			</svg>
		</div>
	</div>
</div>

<style>
	.bar {
		display: flex;
		justify-content: center;
		align-items: center;
		flex-wrap: wrap;
		flex: 0 1 600px;
		margin: 40px;
	}

	h1 {
		text-align: center;
		margin-bottom: 20px;
		font-size: 300%;
	}

	p {
		text-align: justify;
	}

	.logos {
		width: 100%;
		display: flex;
		flex-wrap: wrap;
		justify-content: space-around;
	}

	.logos > img {
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

	.tile-container {
		width: 90%;
	}
</style>
