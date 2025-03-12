<script lang="ts">
	import { APP_NAME, ROOT_TYPES } from '$lib/constants';
	import { pluralize, prettifyRoot, SEMANTIC_CONF } from '$lib/text-format-util';
	import { entToLink } from '$lib/tree-functions';

	import type * as tt from '$lib/tree-types';

	import FullQc from '$lib/components/FullQc.svelte';
	import YearTicks from '$lib/components/YearTicks.svelte';
	import RandTreeLink from '$lib/components/RandTreeLink.svelte';
	import HoverI from '$lib/components/HoverI.svelte';
	import HoverBlock from '$lib/components/HoverBlock.svelte';

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

	function semFunMaker(prefix: string, fun: (r: DecoratedRelated) => string) {
		return (rels: tt.RelatedEntity[]) =>
			prefix + commaAndjoin([...rels.map((r) => fun(toDecorated(r)))]);
	}

	const REL_DESCS = [
		'Papers in fields',
		'Citing in fields',
		'Papers in topics',
		'Collaborations with nation',
		'Published in journal',
		'Authors publishing'
	];

	function toDecorated(r: tt.RelatedEntity): DecoratedRelated {
		let bold = `<b>${r.name}</b>`;
		let link = bold;
		if (ROOT_TYPES.includes(r.etype as tt.RootType)) {
			let href = entToLink({ rootType: r.etype as tt.RootType, semanticId: r.semanticId });
			link = `<a class="ali" href="${href}">${r.name}</a>`;
		}
		return {
			score: r.score,
			name: r.name,
			bold,
			link
		};
	}

	type Semantifyer = {
		fun: (rels: tt.RelatedEntity[]) => string;
		i: number;
	};

	type DecoratedRelated = {
		score: number;
		name: string;
		link: string;
		bold: string;
	};

	function getSemantifyers(rootName: string, rootType: tt.RootType): Semantifyer[] {
		if (rootType == 'authors') {
			return [
				{
					fun: semFunMaker('This includes ', (r) => `${pluralize('paper', r.score)} in ${r.bold}`),
					i: 0
				},
				{
					fun: semFunMaker(
						`${rootName} is often cited by papers focused on `,
						(r) => `${r.name} (${pluralize('paper', r.score)})`
					),
					i: 2
				},
				{
					fun: semFunMaker(
						'The topics of these papers are ',
						(r) => `${r.name} (${pluralize('paper', r.score)})`
					),
					i: 1
				},
				{
					fun: semFunMaker('and collaborates with scholars based in ', (r) => r.link),
					i: 3
				},
				{
					fun: semFunMaker('and has published in prestigious journals such as ', (r) => r.name),
					i: 5
				},
				{
					fun: semFunMaker(
						`${rootName}'s co-authors include `,
						(r) => `${r.link} (${pluralize('paper', r.score)})`
					),
					i: 4
				}
			];
		} else if (rootType == 'institutions') {
			return [
				{
					fun: semFunMaker(
						'Scholars at this organization have produced ',
						(r) => `${pluralize('paper', r.score)} in ${r.name}`
					),
					i: 0
				},
				{
					fun: semFunMaker(
						`Their work is cited by papers focused on `,
						(r) => `${r.name} (${pluralize('citation', r.score)})`
					),
					i: 2
				},
				{
					fun: semFunMaker(
						'on the topics of ',
						(r) => `${r.name} (${pluralize('paper', r.score)})`
					),
					i: 1
				},
				{
					fun: semFunMaker(`Authors at ${rootName} collaborate with scholars in `, (r) => r.link),
					i: 3
				},
				{
					fun: semFunMaker('and has published in prestigious journals including ', (r) => r.name),
					i: 4
				},
				{
					fun: semFunMaker(
						`${rootName}'s authors include `,
						(r) => `${r.name} (${pluralize('paper', r.score)})`
					),
					i: -1
				}
			];
		} else if (rootType == 'countries') {
			return [
				{
					fun: semFunMaker(
						`Scholars in ${rootName} publish mostly in `,
						(r) => `${r.name} (${pluralize('paper', r.score)})`
					),
					i: 0
				},
				{
					fun: semFunMaker(
						'and are cited by scholars working on ',
						(r) => `${r.name} (${pluralize('citation', r.score)})`
					),
					i: 1
				},
				{
					fun: semFunMaker(
						'on the topics of ',
						(r) => `${r.name} (${pluralize('paper', r.score)})`
					),
					i: -1
				},
				{
					fun: semFunMaker(
						`Scholars in ${rootName} collaborate with scholars from `,
						(r) => r.link
					),
					i: 2
				},
				{
					fun: semFunMaker(
						`Scholars in ${rootName} have published in prestigous journals including `,
						(r) => r.name
					),
					i: 4
				},
				{
					fun: semFunMaker(
						`Some of the most productive scholars in ${rootName} are `,
						(r) => `${r.name} (${pluralize('paper', r.score)})`
					),
					i: 3
				}
			];
		}

		return [];
	}

	function getSemanticRels(
		view: tt.View,
		rootName: string,
		rootType: tt.RootType,
		paperText: string,
		citeText: string
	) {
		let semantifyers = getSemantifyers(rootName, rootType);
		const out: string[] = [];
		let id = 0;
		let subs: tt.RelatedEntity[] = [];
		const adder = () => {
			if (id < semantifyers.length) {
				let semI = semantifyers[id];
				out[semI.i] = semI.fun(subs);
			}
		};
		for (const rel of view.primeRelations) {
			if (rel.relType != id) {
				adder();
				id = rel.relType;
				subs = [];
			}
			subs.push(rel);
		}
		if (subs.length > 0) {
			adder();
		}

		let postText = sentenceJoiner(out);
		let prefixes: Record<tt.RootType, string> = {
			authors: `${rootName} has authored ${paperText} that have received a total of ${citeText}`,
			institutions: `In recent decades, authors affiliated with ${rootName} have published ${paperText}, which have received a total of ${citeText}`,
			countries: `In recent decades scholars affiliated with institutions in ${rootName} have published ${paperText}, which have received a total of ${citeText}`,
			sources: ``,
			subfields: ``
		};
		return {
			prefix: prefixes[rootType],
			postText,
			topRels: getTopRels(view)
		};
	}

	function commaAndjoin(parts: string[]) {
		let lastN = parts.length - 1;
		if (lastN == 0) return parts[lastN];
		return [parts.slice(0, lastN).join(', '), parts[lastN]].join(' and ');
	}

	function sentenceJoiner(parts: string[]) {
		const out = [];
		for (let i = 0; i < parts.length - 1; i++) {
			let nextS = parts[i + 1];
			if (nextS.toLowerCase()[0] == nextS[0]) {
				out.push(parts[i]);
			} else {
				out.push(parts[i] + '.');
			}
		}
		out.push(parts[parts.length - 1]);
		return out.join(' ');
	}

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

	let showIndexedCiteText = false;

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

	$: aboutParagraph = getSemanticRels(data.view, rootName, rootType, paperText, citeText);
</script>

<svelte:head>
	<title>{APP_NAME}{titleExtension}</title>
	<meta name="description" content={metaDescriptions} />
	<meta property="og:image" content={data.svgLink} />
</svelte:head>

<div id="head-row" class="shadowy padded marged">
	<div id="name-block">
		<HoverBlock
			show={showIndexedCiteText}
			style={'top: 20svh; left:20vw; width: 60vw;max-width: 550px'}
			>Indexed citations are citations from papers that are loaded into our database to create
			breakdowns of impact. These papers are categorized as articles, are not retracted and have at
			least 1 citation from any work.</HoverBlock
		>
		<div id="nametag">
			<h1>{rootName}</h1>
			<div>
				<span>{paperText}</span>
				and
				<span><a href="/about#indexed-citation" target="blank_">{citeText}</a></span>
				<HoverI bind:hoverToggle={showIndexedCiteText} />.
			</div>
		</div>
		<div id="about">
			<h3>About</h3>
			<div>
				{aboutParagraph.prefix}.
				{@html aboutParagraph.postText}
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
