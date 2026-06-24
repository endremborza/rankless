<script lang="ts">
	import type * as tt from '$lib/tree-types';
	import * as tf from '$lib/tree-functions';
	import { reconstructLoader } from '$lib/loading-functions';
	import FullQc from '$lib/components/FullQc.svelte';
	import { fade } from 'svelte/transition';
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
	import { page } from '$app/state';
	import { APP_NAME, COMPLETE_YEAR, ROOT_TYPES } from '$lib/constants';
	import TreeSvg from '$lib/components/TreeSvg.svelte';
	import { resultsHidden } from '$lib/stores';
	import { prettifyRoot } from '$lib/text-format-util.js';
	import TypeWriter from '$lib/components/TypeWriter.svelte';
	import FeatureShowcase from '$lib/components/FeatureShowcase.svelte';

	let selectedId: string | undefined = undefined;

	function pickId(id: string) {
		return () => {
			selectedId = id;
		};
	}

	function getSpotlights(tops: tt.TopsResponse) {
		let out = [];
		for (const top of tops) {
			let cta = ENTITY_CTA[top.name as tt.RootType];
			if (cta != undefined) out.push({ cta, top });
		}

		return out;
	}

	afterNavigate(() => {
		let anchor = page.url.href.split('#')[1];
		if (anchor) {
			selectedId = anchor;
		}
	});

	const uLogos = [cclLogo, corvLogo, tseLogo];

	const protraits = [
		{
			src: endrePortrait,
			name: 'Endre Borza',
			kicker: 'Engineering',
			role: 'Research Data Engineer & Lead Developer',
			links: [{ href: 'https://www.linkedin.com/in/endremborza/', text: 'LinkedIn' }]
		},
		{
			src: matePortrait,
			name: 'Máté Barkóczi',
			kicker: 'Design',
			role: 'Graphic & Interaction Design',
			links: [{ href: 'https://matebarkoczi.com/', text: 'Portfolio' }]
		},
		{
			src: veraPortrait,
			name: 'Veronika Hamar',
			kicker: 'Operations',
			role: 'Executive Director, CCL',
			links: [{ href: 'www.linkedin.com/in/veronika-hamar-a2b7b716a/', text: 'LinkedIn' }]
		},
		{
			src: cesarPortrait,
			name: 'César A. Hidalgo',
			kicker: 'Director',
			role: 'Director, CCL',
			links: [
				{ href: 'https://cesarhidalgo.com/', text: 'Website' },
				{ href: 'https://x.com/cesifoti', text: 'X' }
			]
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

	const fullLd = '<script type="application/ld+json">' + JSON.stringify(jsonLd) + '</' + 'script>';

	export let data;

	let selectedQcRootId = 0;
	let treeResp: tt.TreeResponse | undefined = data.treeResp;
	let conf: tt.FullTreeConfig = data.conf!;
	let rootName = data.rootName;
	let prefixText = data.prefixText;
	let selectionState: tt.BareNode = {};

	let loader = reconstructLoader(data);
	let props = loader.getTreeSvgProps()!;

	const ENTITY_CTA: Record<tt.RootType, undefined | { kicker: string; cta: string; desc: string }> =
		{
			institutions: {
				kicker: 'Universities',
				cta: 'Explore institutional impact',
				desc: 'Influence by field, geography, and collaboration networks.'
			},
			countries: {
				kicker: 'Countries',
				cta: 'See where knowledge travels',
				desc: 'Which countries cite which - and on what topics.'
			},
			sources: {
				kicker: 'Journals',
				cta: 'Field-shaping venues',
				desc: 'Topical breadth, citation reach, and cross-disciplinary bridges.'
			},
			authors: {
				kicker: 'Scholars',
				cta: 'Individual trajectories',
				desc: 'Track citation origins and topical niches across careers.'
			},
			'hit-papers': undefined,
			subfields: undefined
		};

	$: spotlights = getSpotlights(data.tops);
	let scrollY: number;
	let spotWIdth: number;
	function getViewBox(scrollY: number, i: number, elemW: number) {
		let scRate = Math.min((scrollY || 0) / 1300, 1);
		let scAdd = scRate * 125;
		let scScale = 1 - scRate * 0.2;
		let [x0, y0, fullW, fullH] = [20 * scScale, 130 - scAdd, 230 * scScale, 51];
		let headHeight = 20;
		if (i == -1) return `${x0} ${y0} ${fullW} ${headHeight}`;
		let rate = fullW / (elemW || 1000);
		const [pad, gap] = [26 * rate, 20 * rate];
		let w = (fullW - 2 * pad - 3 * gap) / 4;
		x0 = x0 + pad + i * (gap + w);
		y0 = y0 + pad + headHeight;
		return `${x0} ${y0} ${w} ${fullH - pad - headHeight}`;
	}
	const [bgWidth, bgOffset, bgHeight] = [300, 120, 300];
	let options: tt.RootType[] = ROOT_TYPES.filter((e) => e != 'hit-papers');
	let texts = options.map(prettifyRoot);
</script>

<svelte:head>
	<meta
		name="description"
		content="Explore academic impact beyond rankings. Rankless offers a fresh perspective on how universities influence each geography and topic, emphasizing diverse forms of impact and providing a richer understanding of academic influence."
	/>
	<title>{APP_NAME}</title>
	{@html fullLd}
</svelte:head>
<svelte:window bind:scrollY />

<section class="hero">
	<div class="container hero-inner">
		<div>
			<h1>Explore academic impact - without flattening it into a rank.</h1>
			<p>
				Rankless visualizes the global flow of ideas across universities, journals, scholars, and
				countries - revealing who influences whom, where knowledge travels, and which topics bind
				the world together.
			</p>
			<div class="cta">
				<!-- svelte-ignore a11y_click_events_have_key_events -->
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<!-- svelte-ignore a11y_missing_attribute -->
				<a class="button primary" on:click={() => resultsHidden.set(false)} rel="noopener"
					>🔍 Explore <TypeWriter {texts} /></a
				>
				<a class="button secondary" href="#spotlights">See examples</a>
			</div>
		</div>
		<div id="preview" class="marged hero-art">
			{#if treeResp != undefined && scrollY != undefined}
				<a in:fade out:fade href={tf.entToLink(conf)}>
					<FullQc
						{rootName}
						{selectedQcRootId}
						{conf}
						{prefixText}
						{selectionState}
						fixHeight={false}
						shoPathLevelInfo={false}
						attributeLabels={treeResp.atts}
						completeTree={treeResp.tree}
						treeSpecs={data.treeSpecs}
						setUrl={false}
						allowControls={false}
					/>
				</a>
			{/if}
		</div>
	</div>
</section>

<section id="features">
	<div class="container">
		<h2>Meet the new features</h2>
		<p class="lede spotlead">
			Real profiles, citation trails, and collaboration networks — built from open data and
			explorable in a click.
		</p>
		<FeatureShowcase />
	</div>
</section>

<section id="spotlights">
	<div class="container">
		<h2>Spotlights</h2>
		<p class="lede spotlead">
			Jump straight into examples across institutions, countries, journals, and scholars.
		</p>
		<div class="spotlight" bind:clientWidth={spotWIdth}>
			<TreeSvg
				{...props}
				viewBox={getViewBox(scrollY, -1, spotWIdth)}
				width={bgWidth}
				d2Offset={bgOffset}
				height={bgHeight}
				showText={false}
			/>
			<div class="inner">
				<div class="grid cards">
					{#each spotlights as { cta, top }, i (i)}
						<div class="card">
							<TreeSvg
								{...props}
								viewBox={getViewBox(scrollY, i, spotWIdth)}
								width={bgWidth}
								height={bgHeight}
								d2Offset={bgOffset}
								showText={false}
							/>
							<div class="content">
								<div class="kicker">{cta.kicker}</div>
								<h3>{cta.cta}</h3>
								<p>{cta.desc}</p>
								<div class="links">
									{#each top.entities.slice(0, 3) as ent, __i (__i)}
										<a
											href={tf.entToLink({ rootType: top.name, semanticId: ent.semanticId })}
											target="_blank"
											rel="noopener">{ent.name}</a
										>
									{/each}
								</div>
							</div>
						</div>
					{/each}
				</div>
			</div>
		</div>
	</div>
</section>

<section id="how">
	<div class="container">
		<h2>How does Rankless work?</h2>
		<p class="lede">
			Under the hood, Rankless combines open bibliographic data, network science, and interactive
			design to surface context that rankings miss.
		</p>
		<div class="grid" style="grid-template-columns:repeat(3,minmax(0,1fr));gap:20px">
			<div class="card">
				<!-- <img src="assets/img/universities.svg" alt="Data sources card" /> -->
				<div class="content">
					<div class="kicker">Data pipeline</div>
					<h3>OpenAlex + enhancements</h3>
					<p>
						We build on OpenAlex snapshots and enrich with journal metrics and curated identifiers
						to create a comprehensive citation graph.
					</p>
					<div class="links">
						<a href="https://openalex.org/" target="_blank" rel="noopener">OpenAlex</a>
						<a href="https://www.scimagojr.com/" target="_blank" rel="noopener">SCImago</a>
					</div>
				</div>
			</div>
			<div class="card">
				<!-- <img src="assets/img/journals.svg" alt="Citation graphs card" /> -->
				<div class="content">
					<div class="kicker">Networks</div>
					<h3>Citations, topics, collaborations</h3>
					<p>
						Rankless constructs multi-layer graphs to show influence by domain, geography, and
						co-authorship - so you can follow the story behind the metrics.
					</p>
				</div>
			</div>
			<div class="card">
				<!-- <img src="assets/img/countries.svg" alt="Interactive visuals card" /> -->
				<div class="content">
					<div class="kicker">Exploration</div>
					<h3>Click to go deeper</h3>
					<p>
						Every chart and map is explorable. Click to jump from a bird’s-eye view to institutions,
						journals, and scholars shaping a field.
					</p>
				</div>
			</div>
		</div>
	</div>
</section>

<section id="purpose">
	<div class="container">
		<h2>Why Rankless?</h2>
		<p class="lede">We need to understand more and rank less.</p>
		<p class="lede">
			Rankings flatten complexity into a single number. Rankless restores the context: domain,
			geography, collaboration, and time. Use it to make better-informed decisions - whether you’re
			a student, researcher, policymaker, or funder.
		</p>
		<p>
			Rankless is an experimental data visualization project that allows users to explore the impact
			of thousands of universities. It is built on the idea that universities generate impact that
			is specific to a geography and to certain topics, and that rankings obscure that impact by
			reducing it to a single dimension. By transcending rankings, we highlight a university’s
			multidimensional impact by showing you who they work with and who cites them. To understand
			more, sometimes, we need to rank less.
		</p>
	</div>
</section>

<section id="team">
	<div class="container">
		<h2>Who’s behind it?</h2>
		<p class="lede">
			Rankless is created by the Center for Collective Learning (CCL) at Corvinus University of
			Budapest, with a small, multidisciplinary team.
		</p>
		<div class="grid cards">
			{#each protraits as port, __i (__i)}
				<div class="card">
					<img class="portrait" src={port.src} alt={port.name} />
					<div class="content">
						<div class="kicker">{port.kicker}</div>
						<h3>{port.name}</h3>
						<p>{port.role}</p>
						<div class="links">
							{#each port.links as { text, href }, __i (__i)}
								<a {href} target="_blank" rel="noopener">{text}</a>
							{/each}
						</div>
					</div>
				</div>
			{/each}
		</div>
		<p>
			Rankless was developed at the <a
				href="https://centerforcollectivelearning.org/"
				target="_blank">Center for Collective Learning (CCL)</a
			>
			at <a href="https://www.uni-corvinus.hu/?lang=en" target="_blank">Corvinus University</a> of Budapest
			by a team of four people. The main person behind the project is Endre Borza, an economist working
			as a data engineer who constructed Rankless from the ground up. The graphic and interaction design
			of Rankless is the work of Máté Barkóczi, a designer working on his Master’s at MOME and as an intern
			at CCL. Vera Hamar, Executive Director of CCL, supported Rankless as a project manager and coordinator.
			César A. Hidalgo, Director of CCL, supervised the project.
		</p>

		<p>
			The <a href="https://centerforcollectivelearning.org/" target="_blank"
				>Center for Collective Learning</a
			>
			(CCL) is an interdisciplinary research laboratory with offices in Toulouse, France and Budapest,
			Hungary. For more than a decade, CCL has advanced the state of the art in economic development,
			data visualization, and applications of artificial intelligence. Previous data visualization projects
			by members of CCL include
			<a href="https://oec.world/en" target="_blank">The Observatory of Economic Complexity</a>,
			<a href="https://pantheon.world/" target="_blank">Pantheon</a>, and
			<a href="https://datausa.io/">Data USA</a>, among dozens of others.
		</p>
		<p>
			Rankless was created at the Center for Collective Learning at the Corvinus Institute for
			Advanced Studies (CIAS) at Corvinus University in Budapest. This project was supported by the
			<a href="https://cordis.europa.eu/project/id/101086712" target="_blank"
				>Learn Data ERA Chair</a
			>
			from the European Research Executive Agency.
		</p>
		<h2 id="contact">Contact</h2>
		<p>
			You can reach us by contacting Veronika and Endre directly @
			rankless@&#8203;centerforcollectivelearning.org
		</p>
	</div>
</section>

<section id="faq">
	<div class="container">
		<h1>Frequently Asked Questions</h1>
		<div id="faq-head">
			<div>
				<p>
					Questions and answers about data sources used, update frequency, filtering, impact
					measurement, extensions and visualization.
				</p>
				<p>
					We use <a on:click={pickId('data')} href="#data">open, up-to-date data</a>, process it
					with
					<a on:click={pickId('impact')} href="#impact">transparent methods</a> and visualize the
					results in an
					<a on:click={pickId('viz')} href="#viz">intuitive, unique way</a>.
				</p>
			</div>
		</div>
		<div class="wsized">
			{#each faQuestions as q, __i (__i)}
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
						subset in the tree of <i>i</i> entity, with <i>I</i> being the set of all entities in
						the particular class (in our case, all institutions).
						<i>p(s)</i> is the parent set of <i>s</i> subset, meaning the first complete aggregation
						in the tree above <i>s</i>.
						<i>U<sub>s</sub></i> is a correctional term, to avoid outliers. It is {ALPHA} × 1/<i
							>N<sub>s</sub></i
						>
						where <i>N<sub>s</sub></i> is the number of distinct elements in the subset
					</p>
					<p>
						For one example, Corvinus University has 25.4k citations in our release database, and
						has a specialization metric of 2.12 (which is considered high) for the subset of being
						cited by the University of Bologna. This comes from
					</p>
					<p class="spec-formula">
						<SpecConcrete />
					</p>
					<p>
						as <i>p(s)</i> is the set of all citations, so the corresponding citation count is all of
						them at 25,401, with 129 of them belonging to the subset of the University of Bologna. 0.0023
						is the ratio that is expected due to the size and research output of the University of Bologna.
						The correction term is drawing the ratio toward zero to avoid outliers for subsets with very
						low expected citation counts, with 6587 being the number of entities in the institution class,
						where the University of Bologna belongs.
					</p>
					<p>
						For another example, 0.31 is the specialization metric for the scholars of the
						University of Toronto, publishing papers in Chemistry when the papers are co-authored by
						scholars at Stanford. This is significantly different than the previous example as
						<i>p(s)</i> is not the complete set of all citations which the University of Toronto receives,
						which is over 5 million, but only the subset where the papers were co-authored by authors
						at Stanford, which is about 80 thousand, 1295 of which are on chemistry. Also the subject
						of the metric is chemistry, which is a major concept, a class with 19 elements.
					</p>
					<p class="spec-formula">
						<SpecConcrete2 />
					</p>
				</div>
			</AccordionElement>
		</div>
	</div>
</section>

<div class="logo-strip">
	<h1>Created by</h1>
	{#each uLogos as src, __i (__i)}
		<img class="logo" {src} alt="inst-logo" />
	{/each}
</div>
<div class="logo-strip" id="support-strip">
	<img
		class="logo"
		src={euLogo}
		alt="European Union Logo"
		style="width: 320px; margin-bottom: 20px;"
	/>
</div>

<style>
	:root {
		--maxw: 1200px;
	}
	.container {
		max-width: var(--maxw);
		margin: 0 auto;
	}

	.hero-inner {
		display: grid;
		grid-template-columns: 1.1fr 0.9fr;
		gap: 40px;
		align-items: center;
		padding: 48px 0;
	}
	.hero h1 {
		font-size: 56px;
		line-height: 1.05;
		margin: 0 0 12px 0;
		font-weight: 800;
		letter-spacing: -0.02em;
	}
	.hero p {
		font-size: 18px;
		color: var(--muted);
		margin: 0 0 24px 0;
	}
	.cta {
		display: flex;
		gap: 12px;
		flex-wrap: wrap;
	}
	.button {
		display: inline-flex;
		align-items: center;
		gap: 10px;
		background: linear-gradient(135deg, var(--accent-text), var(--highlight-text));
		padding: 14px 18px;
		color: var(--text-bg);
		border: 0;
		font-weight: 700;
		box-shadow: 0 10px 30px rgba(var(--color-range-25), 0.3);
		cursor: pointer;
	}
	.button.primary {
		width: 260px;
	}
	.button.secondary {
		color: var(--color-text);
		background: transparent;
		border: 2px solid rgba(var(--color-range-65), 0.35);
	}
	.hero-art {
		height: 40svh;
	}
	section {
		padding: 56px 0;
	}
	section h2 {
		font-size: 32px;
		letter-spacing: -0.01em;
		margin: 0 0 10px 0;
	}

	p {
		text-align: justify;
	}
	.lede {
		font-weight: 600;
		font-size: 1.2rem;
	}
	.spotlead {
		text-align: center;
	}
	.grid {
		display: grid;
		gap: 20px;
	}
	.grid.cards {
		grid-template-columns: repeat(4, minmax(0, 1fr));
	}
	.card {
		background: var(--card);
		border: 1px solid rgba(148, 163, 184, 0.18);
		overflow: hidden;
		display: flex;
		flex-direction: column;
		transition:
			transform 0.2s ease,
			box-shadow 0.2s ease;
	}
	.card:hover {
		transform: translateY(-4px);
		box-shadow: 0 16px 50px rgba(0, 0, 0, 0.35);
	}
	.card img {
		width: 100%;
		/*height: 180px;*/
		object-fit: cover;
		border-bottom: 1px solid rgba(148, 163, 184, 0.12);
	}
	.card .content {
		padding: 16px;
	}
	.card .kicker {
		color: #a5b4fc;
		font-weight: 700;
		font-size: 12px;
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}
	.card h3 {
		margin: 6px 0 8px 0;
		font-size: 18px;
	}
	.card p {
		margin: 0;
		color: var(--muted);
		font-size: 14px;
		font-weight: 400;
		text-align: left;
	}

	.portrait {
		height: 330px;
	}

	.links {
		display: flex;
		gap: 10px;
		flex-wrap: wrap;
		margin-top: 12px;
	}
	.links a {
		padding: 6px 10px;
		border: 1px solid rgba(148, 163, 184, 0.25);
		background: rgba(148, 163, 184, 0.08);
	}
	.spotlight {
		position: relative;
		margin-top: 10px;
		overflow: hidden;
		border: 1px solid rgba(148, 163, 184, 0.2);
	}

	.spotlight .inner {
		padding: 26px;
	}

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

	a {
		text-decoration: underline;
		/* color: var(--color-theme-darkgrey3); */
	}

	#support-strip {
		background-color: var(--color-theme-darkgrey2);
		padding-bottom: 5px;
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

	.logo-strip {
		justify-content: center;
		display: flex;
		flex-wrap: wrap;
	}

	.logo-strip > h1 {
		width: 100%;
		text-align: center;
		margin-bottom: 0px;
		margin-top: 10px;
		font-size: 1.7rem;
	}

	@container (min-width: 400px) {
		p {
			text-align: justify;
		}
	}

	@media (max-width: 1300px) {
		section {
			margin-left: var(--unified-margin);
			margin-right: var(--unified-margin);
		}
	}
	@media (max-width: 1000px) {
		.hero-inner {
			grid-template-columns: 1fr;
		}
		.grid.cards {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}
	@media (max-width: 540px) {
		.hero h1 {
			font-size: 36px;
		}
		.grid.cards {
			grid-template-columns: 1fr;
		}
	}
</style>
