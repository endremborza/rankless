<script lang="ts">
	import FullQc from '$lib/components/FullQc.svelte';
	import type * as tt from '$lib/tree-types';
	import * as tf from '$lib/tree-functions';
	import { onMount } from 'svelte';
	import { BE_REMOTE_URL } from '$lib/constants';
	import { SEMANTIC_CONF, prettifyRoot } from '$lib/text-format-util';
	import TextedLogo from '$lib/components/TextedLogo.svelte';
	import { fade } from 'svelte/transition';

	export let data;
	let mounted = false;
	const loadMs = 400;
	const selShift = loadMs * 3;

	let innerHeight: number;
	let innerWidth: number;

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
		let resps = Object.values(treeResps);
		if (resps.length == 0) {
			return;
		}
		let tree = resps[0]?.tree;
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
			let prepKs: [number, string][] = Object.entries(tree.children || {}).map(([k, v]) => [
				v.linkCount,
				k
			]);
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

	function loadSelected(selInds: [number, number]) {
		if (mounted) {
			const [i, j] = selInds;
			if (i < 0) {
				return;
			}
			clearInterval(selectorInterval);
			setTimeout(() => {
				if (selectedInds[0] == i && selectedInds[1] == j) {
					setTree(data.tops[i].name, data.tops[i].entities[j]);
				}
			}, loadMs);
		}
	}

	function setTree(rootType: tt.RootType, e: tt.SearchResult) {
		let year = tf.getDefaultYear(rootType);
		let treeCount = data.treeSpecs.specs[rootType].length;
		let confBase: tt.FullTreeConfig = {
			semanticId: e.semanticId,
			year,
			treeId: Math.floor(Math.random() * treeCount),
			rootType
		};
		fetch(tf.treeBeUrl(BE_REMOTE_URL, confBase, 1))
			.then((res) => res.json())
			.then((resp) => {
				let rObj: Record<string, tt.TreeResponse> = {};
				rObj[e.semanticId] = resp;
				[conf, treeResps, prefixText, rootName, selectionState] = [
					confBase,
					rObj,
					SEMANTIC_CONF[rootType]?.start || '',
					e.name,
					{}
				];
				clearInterval(selectorInterval);
				selectorInterval = setInterval(randSelect, selShift);
			});
	}

	let conf: tt.FullTreeConfig = data.conf;
	let treeResps: Record<string, tt.TreeResponse> = { '0-0': data.treeResp };
	let rootName = data.rootName;
	let selectedQcRootId = 0;
	let prefixText = data.prefixText;
	let selectionState: tt.BareNode = {};

	$: loadSelected(selectedInds);
</script>

<div id="land-header">
	<span>
		<TextedLogo varColor={'color-text'} pad={0} size={30} />
	</span>
</div>

<div id="tops">
	<div id="init-list" class="marged">
		{#each data.tops.entries() as [i, entityTop]}
			{#if entityTop.entities.length > 0}
				<h3>{prettifyRoot(entityTop.name)}</h3>
				{#each entityTop.entities.slice(0, 3).entries() as [j, ent]}
					<a
						href={tf.entToLink({ ...ent, rootType: entityTop.name })}
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
						{ent.name}
					</a>
				{/each}
			{/if}
		{/each}
	</div>
	<div bind:clientWidth={innerWidth} bind:clientHeight={innerHeight} id="preview" class="marged">
		{#each Object.entries(treeResps) as [_k, treeResp]}
			<a in:fade out:fade href={tf.entToLink(conf)}>
				<FullQc
					{rootName}
					{selectedQcRootId}
					{conf}
					{prefixText}
					{selectionState}
					attributeLabels={treeResp.atts}
					completeTree={treeResp.tree}
					treeSpecs={data.treeSpecs}
					removeHighlightUnhover={false}
					setUrl={false}
					allowControls={false}
					{innerHeight}
					{innerWidth}
				/>
			</a>
		{/each}
	</div>
</div>

<style>
	.focused {
		background: var(--color-theme-red);
		color: var(--color-theme-black);
		font-weight: 700;
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

	#init-list > a {
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
		/* pointer-events: none; */
	}
</style>
