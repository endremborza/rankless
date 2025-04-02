<script lang="ts">
	import FullQc from '$lib/components/FullQc.svelte';
	import TypeWriter from '$lib/components/TypeWriter.svelte';
	import type * as tt from '$lib/tree-types';
	import * as tf from '$lib/tree-functions';
	import { onMount } from 'svelte';
	import { BE_REMOTE_URL } from '$lib/constants';
	import { page } from '$app/stores';
	import { SEMANTIC_CONF, prettifyRoot } from '$lib/text-format-util';
	import TextedLogo from '$lib/components/TextedLogo.svelte';
	import Webby from '$lib/components/Webby.svelte';

	export let data;
	let mounted = false;
	const loadMs = 400;
	const selShift = loadMs * 6;

	let innerHeight: number;
	let innerWidth: number;

	let texts = ['topics', 'geographies', 'publications', 'relationships'];
	let wordInd = 0;

	let selectorInterval: number;
	let selectedInds: [number, number] = [0, 0];
	let indsOfAnim: [number, number] = [-1, 0];
	onMount(() => {
		mounted = true;
		selectorInterval = setInterval(randSelect, selShift);
	});

	function getRandElem<T>(l: T[]) {
		return l[Math.floor(Math.random() * l.length)];
	}

	function randSelect() {
		let tree = treeResp?.tree;
		if (tree != undefined) {
			if (indsOfAnim[0] != selectedInds[0] || indsOfAnim[1] != selectedInds[1]) {
				indsOfAnim = selectedInds;
				return;
			}
			let ksIn = Object.keys(selectionState?.children || {});
			const drop = () => {
				if (Math.random() > 0.5) {
					ksIn.pop();
				} else {
					ksIn.splice(0, 1);
				}
			};
			let prepKs = Object.entries(tree.children || {}).map(([k, v]) => [v.linkCount, k]);
			prepKs.sort((l, r) => l[0] - r[0]);
			let ks = prepKs.map(([_, k]) => k).slice(-6);
			// let ks = Object.keys(tree.children || {}).slice(0, 7);
			if (ksIn.length > 2) {
				drop();
			} else if (ksIn.length == 2 && Math.random() > 0.6) {
				drop();
			} else {
				ksIn.push(getRandElem(ks));
			}
			let children = Object.fromEntries(ksIn.map((k) => [k, {}]));
			selectionState = { children };
		}
	}

	function loadSelected(selInds: [number, number], tops: tt.TopsResponse, mounted: boolean) {
		if (mounted) {
			const [i, j] = selInds;
			if (i < 0) {
				return;
			}
			// clearInterval(selectorInterval);
			setTimeout(() => {
				if (selectedInds[0] == i && selectedInds[1] == j) {
					setTree(tops[i].name, tops[i].entities[j]);
				}
			}, loadMs);
		}
	}

	function setTree(rootType: tt.RootType, e: tt.SearchResult) {
		let spec: tt.ShareSpec = tf.parseLinkWithParams($page.url.searchParams, rootType);

		let treeCount = data.treeSpecs.specs[rootType].length;

		let confBase: tt.FullTreeConfig = {
			semanticId: e.semanticId,
			year: spec.year,
			treeId: Math.floor(Math.random() * treeCount),
			rootType
		};
		fetch(tf.treeBeUrl(BE_REMOTE_URL, confBase, 1))
			.then((res) => res.json())
			.then((resp) => {
				[conf, treeResp, prefixText, rootName, selectionState] = [
					confBase,
					resp,
					SEMANTIC_CONF[rootType]?.start || '',
					e.name,
					{}
				];
			});
	}

	let conf: tt.FullTreeConfig | undefined;
	let treeResp: tt.TreeResponse | undefined;
	let rootName = '';
	let selectedQcRootId = 0;
	let prefixText = '';
	let selectionState: tt.BareNode = {};

	$: loadSelected(selectedInds, data.tops, mounted);
</script>

<div id="land-header">
	<span>
		<TextedLogo varColor={'color-text'} pad={0} size={30} />
	</span>
</div>

<div id="tops">
	<div id="init-list" class="marged">
		<Webby />
		{#each data.tops.entries() as [i, entityTop]}
			<h3>{prettifyRoot(entityTop.name)}</h3>
			{#each entityTop.entities.slice(0, 3).entries() as [j, ent]}
				<span
					role="none"
					on:mouseover={() => {
						selectedInds = [i, j];
					}}
					on:mouseleave={() => {
						selectedInds = [-1, -1];
					}}
					on:focus={() => {
						selectedInds = [i, j];
					}}
					class={selectedInds[0] == i && selectedInds[1] == j ? 'focused' : ''}
				>
					<a href={tf.entToLink({ ...ent, rootType: entityTop.name })}>{ent.name}</a>
				</span>
			{/each}
		{/each}
	</div>
	<div bind:clientWidth={innerWidth} bind:clientHeight={innerHeight} id="preview" class="marged">
		{#if conf != undefined && treeResp != undefined}
			<FullQc
				{rootName}
				{selectedQcRootId}
				{conf}
				{prefixText}
				{selectionState}
				treeSpecs={data.treeSpecs}
				removeHighlightUnhover={false}
				setUrl={false}
				allowControls={false}
				attributeLabels={treeResp.atts}
				completeTree={treeResp.tree}
				{innerHeight}
				{innerWidth}
			/>
		{/if}
	</div>
</div>

<style>
	.focused {
		background: var(--color-theme-red);
	}

	.focused > a {
		color: var(--color-theme-darkblue);
	}

	#land-header {
		position: fixed;
		top: 0px;
		height: 7svh;
		z-index: 1;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 100%;
	}

	#land-header > span {
		width: min(390px, 60vw);
		font-size: min(1.4rem, 4vw);
		left: 20vw;
	}

	#tops {
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
	}

	#tops > div {
		height: 80svh;
	}

	#init-list {
		flex: 4;
		overflow-y: scroll;
		display: flex;
		flex-direction: column;
		gap: var(--unified-margin);
		padding-left: var(--unified-padding);
		padding-right: var(--unified-padding);
	}

	#init-list > span {
		min-width: 180px;
		padding: 6px;
		border-bottom: solid var(--color-theme-blue) 3px;
		-webkit-transition: background-color 500ms linear;
		-ms-transition: background-color 500ms linear;
		transition: background-color 500ms linear;
		/* background: rgba(var(--color-range-15), 0.1); */
	}

	#preview {
		min-width: 360px;
		flex: 8;
		pointer-events: none;
	}
</style>
