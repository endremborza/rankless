<script lang="ts">
	import cclLogo from '$lib/assets/images/icons/ccl-logo.png';
	import corvLogo from '$lib/assets/images/icons/corv-logo.png';

	import euLogo from '$lib/assets/images/icons/eu-logo.png';
	import tseLogo from '$lib/assets/images/icons/tse-logo.png';

	import cesarPortrait from '$lib/assets/images/portraits/cesar.jpg';
	import endrePortrait from '$lib/assets/images/portraits/endre.jpg';
	import veraPortrait from '$lib/assets/images/portraits/vera.jpg';
	import matePortrait from '$lib/assets/images/portraits/mate.jpg';

	import AccordionElement from '$lib/components/AccordionElement.svelte';
	import SpecCalcMath from '$lib/components/SpecCalcMath.svelte';
	import { ALPHA } from '$lib/metric-calculation';
	import SpecConcrete from '$lib/components/SpecConcrete.svelte';
	import SpecConcrete2 from '$lib/components/SpecConcrete2.svelte';
	import { afterNavigate } from '$app/navigation';
	import { page } from '$app/stores';
	import { COMPLETE_YEAR } from '$lib/constants';

	let selectedId: string | undefined = undefined;

	function pickId(id: string) {
		return () => {
			selectedId = id;
		};
	}

	afterNavigate(() => {
		let anchor = $page.url.href.split('#')[1];
		if (anchor) {
			selectedId = anchor;
		}
	});

	const uLogos = [cclLogo, corvLogo, tseLogo];

	const protraits = [
		{ src: endrePortrait, name: 'Endre Borza', role: 'Research Data Engineer, CCL' },
		{ src: matePortrait, name: 'Máté Barkóczi', role: 'Designer, CCL' },
		{ src: veraPortrait, name: 'Veronika Hamar', role: 'Executive Director, CCL' },
		{
			src: cesarPortrait,
			name: 'César A. Hidalgo',
			role: 'Director, CCL',
			href: 'https://cesarhidalgo.com/'
		}
	];

	const faQuestions = [
		{
			question: 'What are your data-sources?',
			id: 'data',
			answer: `
			We use the latest <a href="https://docs.openalex.org/download-all-data/openalex-snapshot"
				target="_blank">OpenAlex snapshot</a>
			as our main data source and expand it using journal classification and impact factor estimates
			from
			<a href="https://www.scimagojr.com/" target="_blank">Scimago</a>.
		`
		},
		{
			question: 'What are indexed citations?',
			id: 'indexed-citation',
			answer: `
			Indexed citations are citations from papers that are pre-filtered to appear in our database. Currently these are works categorized as 'article' by OpenAlex, non-retracted, and noted to have at least 1 citation from any source.
		`
		},
		{
			question: 'Can I download/export Rankless data?',
			id: 'export',
			answer: `
			Since we are secondary users of data sources, we recommend people to download the data
			directly from these sources (mainly OpenAlex).
		`
		},
		{
			question: 'How often do you update your data?',
			id: 'frequency',
			answer: `
			Our current workflow considers monthly updates.
		`
		},
		{
			question: 'How accurate is your data?',
			id: 'accuracy',
			answer: `
			The accuracy of our data depends on the quality of the entity resolution provided by OpenAlex.
		`
		},
		{
			question: 'Do you filter the data?',
			id: 'data-filter',
			answer: `
			We consider only non-retracted publications with no more than 20 authors that were published
			after ${COMPLETE_YEAR}, and have been cited at least once. Additionally, we only consider
			publication sources and institutions with at least 200 and 500 of such papers respectively.
		`
		},
		{
			question: 'How do you assign papers and journals to subject categories?',
			id: 'classification',
			answer: `
			We use OpenAlex's hierarchy of <a href="https://docs.openalex.org/api-entities/topics"
				target="_blank">topics</a>
			for each piece of work, based on the contents, references, source, etc. We assign topics to a
			paper
			with a match score of over 0.6.
		`
		},
		{
			question: 'How do you measure impact?',
			id: 'impact',
			answer: `
			Our impact flows are based on citations, but in some cases we make use of coathorships to
			visualize relationships between institutions. In all cases, the number of citations are noted
			in the charts.
		`
		},
		{
			question: 'What kind of visualization engine do you use?',
			id: 'viz',
			answer: `
			All our visualizations are hand-rolled SVGs with css transitions, made with <a
				href="https://svelte.dev/" target="_blank">svelte</a>.
		`
		}
	];

	const ldInnards = faQuestions.map((e) => {
		return {
			'@type': 'Question',
			name: e.question,
			acceptedAnswer: {
				'@type': 'Answer',
				text: e.answer
			}
		};
	});

	const jsonLd = {
		'@context': 'https://schema.org',
		'@type': 'FAQPage',
		name: 'Rankless FAQ',
		mainEntity: ldInnards
	};

	const fullLd = '<script type="application/ld+json">' + JSON.stringify(jsonLd) + `<\/script>`;
</script>

<svelte:head>
	{@html fullLd}
</svelte:head>

<h1>About</h1>
<h2>We need to understand more and rank less</h2>

<p class="btxt">
	Rankless is an experimental data visualization project that allows users to explore the impact of
	thousands of universities. It is built on the idea that universities generate impact that is
	specific to a geography and to certain topics, and that rankings obscure that impact by reducing
	it to a single dimension. By transcending rankings, we highlight a university’s multidimensional
	impact by showing you who they work with and who cites them. To understand more, sometimes, we
	need to rank less.
</p>

<h1>Our Team</h1>

<p class="btxt">
	Rankless was developed at the <a href="https://centerforcollectivelearning.org/" target="_blank"
		>Center for Collective Learning (CCL)</a
	>
	at <a href="https://www.uni-corvinus.hu/?lang=en" target="_blank">Corvinus University</a> of Budapest
	by a team of four people. The main person behind the project is Endre Borza, an economist working as
	a data engineer who constructed Rankless from the ground up. The graphic and interaction design of
	Rankless is the work of Máté Barkóczi, a designer working on his Master’s at MOME and as an intern
	at CCL. Vera Hamar, Executive Director of CCL, supported Rankless as a project manager and coordinator.
	César A. Hidalgo, Director of CCL, supervised the project.
</p>

<div class="bstrip" id="person-bar">
	<div class="bar">
		{#each protraits as port}
			<div class="person">
				<img class="portrait" src={port.src} alt={port.name} />
				<p><a href={port.href} target="_blank">{port.name}</a></p>
				<p class="prole">{port.role}</p>
			</div>
		{/each}
	</div>
</div>
<div class="btxt">
	<p>
		The <a href="https://centerforcollectivelearning.org/" target="_blank"
			>Center for Collective Learning</a
		>
		(CCL) is an interdisciplinary research laboratory with offices in Toulouse, France and Budapest,
		Hungary. For more than a decade, CCL has advanced the state of the art in economic development, data
		visualization, and applications of artificial intelligence. Previous data visaualization projects
		by members of CCL include
		<a href="https://oec.world/en" target="_blank">The Observatory of Economic Complexity</a>,
		<a href="https://pantheon.world/" target="_blank">Pantheon</a>, and
		<a href="https://datausa.io/">Data USA</a>, among dozens of others.
	</p>
	<p>
		Rankless was created at the Center for Collective Learning at the Corvinus Institute for
		Advanced Studies (CIAS) at Corvinus University in Budapest. This project was supported by the
		<a href="https://cordis.europa.eu/project/id/101086712" target="_blank">Learn Data ERA Chair</a>
		from the European Research Executive Agency.
	</p>
	<h1 id="contact">Contact</h1>
	<p>
		You can reach us by contacting Veronika and Endre directly @
		rankless@&#8203;centerforcollectivelearning.org
	</p>
</div>
<div class="bstrip">
	<h1 id="faq">Frequently Asked Questions</h1>
	<div id="faq-head">
		<div class="btxt">
			<p>
				Questions and answers about data sources used, update frequency, filtering, impact
				measurement, extensions and visualization.
			</p>
			<p>
				We use <a on:click={pickId('data')} href="#data">open, up-to-date data</a>, process it with
				<a on:click={pickId('impact')} href="#impact">transparent methods</a> and visualize the
				results in an
				<a on:click={pickId('viz')} href="#viz">intuitive, unique way</a>.
			</p>
		</div>
	</div>
	<div class="wsized">
		{#each faQuestions as q}
			<AccordionElement bind:selectedId title={q.question} id={q.id}>
				{@html q.answer}
			</AccordionElement>
		{/each}
		<AccordionElement bind:selectedId title="How do you measure specialization?" id="spec">
			<div id="faq-explanation">
				<p>
					We use a modified version of the <a
						href="https://en.wikipedia.org/wiki/Revealed_comparative_advantage"
						target="_blank">Revealed Comparative Advantage (RCA)</a
					>
					metric introduced by the Hungarian economist Bela Balassa. RCA is the ratio between the observed
					and expected observations in a dataset. It is also known as the Location Quotients (LQ) in
					urban planning and economic geography or as Lift in data mining and computer science.
				</p>
				<p>Precisely, specialization is measured using the following formula:</p>
				<p class="spec-formula">
					<SpecCalcMath />
				</p>
				<p>
					Where <i>S<sub>i,s</sub></i> is the specialization metric corresponding to the
					<i>s</i>
					subset in the tree of <i>i</i> entity (say an institution).
					<i>C<sub>i,s</sub></i> is the number of citations corresponding to the <i>s</i>
					subset in the tree of <i>i</i> entity, with <i>I</i> being the set of all entities in the
					particular class (in our case, all institutions).
					<i>p(s)</i> is the parent set of <i>s</i> subset, meaning the first complete aggregation
					in the tree above <i>s</i>.
					<i>U<sub>s</sub></i> is a correctional term, to avoid outliers. It is {ALPHA} × 1/<i
						>N<sub>s</sub></i
					>
					where <i>N<sub>s</sub></i> is the number of distinct elements in the subset
				</p>
				<p>
					For one example, Corvinus University has 25.4k citations in our release database, and has
					a specialization metric of 2.12 (which is considered high) for the subset of being cited
					by the University of Bologna. This comes from
				</p>
				<p class="spec-formula">
					<SpecConcrete />
				</p>
				<p>
					as <i>p(s)</i> is the set of all citations, so the corresponding citation count is all of them
					at 25,401, with 129 of them belonging to the subset of the University of Bologna. 0.0023 is
					the ratio that is expected due to the size and research output of the University of Bologna.
					The correction term is drawing the ratio toward zero to avoid outliers for subsets with very
					low expected citation counts, with 6587 being the number of entities in the institution class,
					where the University of Bologna belongs.
				</p>
				<p>
					For another example, 0.31 is the specialization metric for the scholars of the University
					of Toronto, publishing papers in Chemistry when the papers are co-authored by scholars at
					Stanford. This is significantly different than the previous example as
					<i>p(s)</i> is not the complete set of all citations which the University of Toronto receives,
					which is over 5 million, but only the subset where the papers were co-authored by authors at
					Stanford, which is about 80 thousand, 1295 of which are on chemistry. Also the subject of the
					metric is chemistry, which is a major concept, a class with 19 elements.
				</p>
				<p class="spec-formula">
					<SpecConcrete2 />
				</p>
			</div>
		</AccordionElement>
	</div>
</div>
<div class="bstrip logo-strip">
	<h1>Created by</h1>
	{#each uLogos as src}
		<img class="logo" {src} alt="inst-logo" />
	{/each}
</div>
<div class="bstrip logo-strip" id="support-strip">
	<h1>Supported by</h1>
	<img
		class="logo"
		src={euLogo}
		alt="European Union Logo"
		style="width: 320px; margin-bottom: 20px;"
	/>
</div>

<style>
	h1 {
		text-align: center;
		font-size: 2.9rem;
		margin: 30px;
	}

	h2 {
		text-align: center;
		padding-right: 15px;
		padding-left: 15px;
	}

	p {
		font-weight: 600;
		font-size: 1.2rem;
		max-width: 1180px;
		margin-left: auto;
		margin-right: auto;
	}

	a {
		text-decoration: underline;
		/* color: var(--color-theme-darkgrey3); */
	}

	#person-bar {
		padding-top: 80px;
		padding-bottom: 80px;
		background-color: var(--color-theme-lightblue);
	}

	#support-strip {
		background-color: var(--color-theme-darkgrey2);
		padding-bottom: 5px;
	}

	#support-strip > h1 {
		color: var(--color-theme-white);
	}

	#faq-head {
		width: 100%;
		display: flex;
		justify-content: center;
	}

	#faq-explanation > p {
		font-size: 1rem;
		font-weight: 100;
	}

	.spec-formula {
		width: 100%;
		display: flex;
		justify-content: center;
	}

	.wsized {
		width: 1000px;
		max-width: 90vw;
		margin-bottom: 40px;
	}

	.btxt {
		font-weight: 400;
		text-align: justify;
		padding-left: 35px;
		padding-right: 35px;
		margin-top: 100px;
		margin-bottom: 60px;
		/* color: var(--color-theme-darkgrey); */
	}

	@media (max-width: 768px) {
		.btxt {
			text-align: left;
		}
	}

	.prole {
		font-weight: 300;
	}

	.bar {
		flex: 0 1 1400px;
		display: flex;
		justify-content: center;
		align-items: center;
		flex-wrap: wrap;
	}

	.portrait {
		margin: 30px;
		height: 274px;
		width: 250px;
		box-shadow: 7px 7px 17px var(--color-theme-shadow);
	}

	.person > p {
		text-align: center;
	}

	.btxt > p {
		font-weight: 400;
	}

	.logo-strip > h1 {
		width: 100%;
		text-align: center;
		margin-bottom: 0px;
		margin-top: 10px;
		font-size: 1.7rem;
	}
</style>
