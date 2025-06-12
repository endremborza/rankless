<script lang="ts">
	import { onMount } from 'svelte';

	import type * as tt from '$lib/tree-types';
	import * as tf from '$lib/tree-functions';

	import countryPaths from '$lib/assets/data/country-svg-paths.json';
	// import countryBoxes from '$lib/assets/data/country-svg-boxes.json';
	import { getColor, getColorArr } from '$lib/style-util';
	import { formatNumber } from '$lib/text-format-util';
	import { BE_REMOTE_URL, HIGH_OP, LOW_OP } from '$lib/constants';
	import PathLevelInfoBox from './PathLevelInfoBox.svelte';

	export let rootName = '';
	export let rootId: number;
	export let countryL1Specs: number[];
	export let conf: tt.FullTreeConfig;
	export let treeSpecs: tt.TreeSpecs;
	export let resp: tt.TreeResponse | undefined;
	export let treeId = countryL1Specs[0];

	type LevelT = tt.OMap<{ w: number; id: number }>;

	let year = treeSpecs.yearBreaks[0]; //conf.year;
	let countryLevels: LevelT = {};
	let mounted = false;
	let highlighted = '';
	let highlightedRate: undefined | number;
	let infoPath: number[] = [];

	let minOp = LOW_OP * 0.5;
	let maxOp = HIGH_OP * 1.2;
	let mainColorRate = 0.5;

	let xMin = 0;
	let yMin = -20;
	let mapWidth = 2000;
	let mapHeight = 950;
	let maxw: undefined | number;
	let minw: undefined | number;
	let svgEl: SVGSVGElement;
	let styleEl: SVGStyleElement | null = null;
	const TOP_N = 200;

	let currentTreeSpec = treeSpecs.specs[conf.rootType][treeId];
	let selectedBreakdowns = tf.getDefaultBreakdowns(currentTreeSpec);
	let isSpec = false;

	$: levelOptions = tf.fillBreakdownOptions(
		countryL1Specs.map((e) => [e, treeSpecs.specs[conf.rootType][e]]),
		1
	);

	function classNamer(s: string) {
		return `country-${s.toLowerCase().replaceAll(' ', '-')}`;
	}

	function getClassStyles(levels: LevelT, highlighted: string) {
		maxw = undefined;
		minw = undefined;
		for (const { w } of Object.values(levels)) {
			if (maxw == undefined || w > maxw) {
				maxw = w;
			}
			if (minw == undefined || w < minw) {
				minw = w;
			}
		}
		let wspan = (maxw || 1) - (minw || 0);
		const scaler = (w: number) => ((w - (minw || 0)) / wspan) * (maxOp - minOp) + minOp;
		const sLines = [];
		for (const [c, { w }] of Object.entries(levels)) {
			let lineColor = getColor(mainColorRate);
			let isHighlighted = c == highlighted;
			let opa = scaler(w) / 100;
			let line = `fill: ${lineColor}; fill-opacity: ${opa};`;
			if (isHighlighted) {
				line += `stroke-width: 4.5;`;
			}
			sLines.push(`path.${classNamer(c)} {${line}}`);
		}
		return sLines.join('\n');
	}

	function updateL1(visTree: tt.TreeInfo | undefined) {
		if (visTree == undefined) return;
		if (resp == undefined) return;
		let l1Type = 'countries' as tt.RootType;
		try {
			let l1Kv = Object.entries(visTree.tree.children).map(([k, v]) => [
				resp.atts[l1Type][k].name,
				{ w: v.weight, id: k }
			]);
			countryLevels = Object.fromEntries(l1Kv);
		} catch (error) {
			// console.log(error);
		}
	}

	function getVisTree(resp: tt.TreeResponse | undefined, globConf: tt.FullControlSpecs) {
		if (resp == undefined) return undefined;
		return tf.deriveVisibleTree(resp.tree, globConf, {}, resp.atts, currentTreeSpec);
	}

	function updateTreeId(bSelected: string[], bdOptions: tt.BreakdownOptions) {
		let bop = bSelected[0];
		let treeIds = bdOptions[bop]?.treeSpecs || [];
		if (treeIds.length == 0) {
			for (const [k, v] of Object.entries(bdOptions)) {
				if (v.treeSpecs.length > 0) {
					[bSelected[0], treeId] = [k, v.treeSpecs[0]];
				}
				return;
			}
		}
		if (!(treeId in treeIds)) {
			treeId = treeIds[0];
		}
	}

	function updateStyle(styleEl: SVGStyleElement | null, l1Weights: LevelT, highlighted: string) {
		if (styleEl == undefined) return;
		styleEl.textContent = getClassStyles(l1Weights, highlighted);
	}
	function reloadResp(treeId: number, year: number, _rootId: number) {
		if (mounted == false) return;
		let newConf: tt.FullTreeConfig = { ...conf, treeId, year, wide: true };
		fetch(tf.treeBeUrl(BE_REMOTE_URL, newConf, 0)).then((res) => {
			res
				.json()
				.then((jsv: tt.TreeResponse) => {
					resp = jsv;
				})
				.catch((e) => {
					console.error('error', e);
				});
		});
	}

	onMount(() => {
		const svgNS = 'http://www.w3.org/2000/svg';
		styleEl = document.createElementNS(svgNS, 'style') as SVGStyleElement;
		svgEl.insertBefore(styleEl, svgEl.firstChild);
		mounted = true;
		if (resp == undefined) {
			reloadResp(treeId, year, rootId);
		}
	});

	let globConf: tt.FullControlSpecs;

	$: globConf = {
		globalSizeBase: isSpec ? 'specialization' : 'volume',
		globalLimit: TOP_N,
		levelSpecs: [tf.DEFAULT_CONTROL_SPEC]
	};
	$: visibleTreeInfo = getVisTree(resp, globConf);
	$: isRefSide = (selectedBreakdowns[0] || '').split('-')[1] == 'true';
	$: weightText = isSpec
		? 'Revealed comparative advantage'
		: isRefSide
		? 'Total citations of papers'
		: 'Citations';
	$: updateTreeId(selectedBreakdowns, levelOptions);
	$: updateL1(visibleTreeInfo);
	$: updateStyle(styleEl, countryLevels, highlighted);
	$: reloadResp(treeId, year, rootId);

	let clicked = false;
	function setHover(cc: string) {
		return () => {
			if (!clicked) {
				highlighted = cc;
				if (cc in countryLevels) {
					infoPath = [countryLevels[cc].id];
					if (maxw != undefined && minw != undefined) {
						highlightedRate = (countryLevels[cc].w - minw) / (maxw - minw);
					}
				} else {
					infoPath = [];
					highlightedRate = undefined;
				}
			}
		};
	}

	function getGradient() {
		let steps = [
			`rgba(${getColorArr(mainColorRate)}, ${minOp}%) 0%`,
			`rgba(${getColorArr(mainColorRate)}, ${maxOp}%) 100%`
		];
		// for (const [i, cr] of colorRates.entries()) {
		// 	let pct = (100 * i) / (colorRates.length - 1);
		// 	steps.push(`rgba(${getColorArr(cr)}, ${baselineOp}) ${pct}%`);
		// }
		return `linear-gradient(to right, ${steps.join(', ')})`;
	}

	// type CountryBd = 'countries-true' | 'countries-false';
	const C_SEM_MAP: Record<tt.RootType, Record<string, string>> = {
		countries: {
			'countries-true': 'collaborating with authors based in',
			'countries-false': 'citing scholars based in'
		},
		institutions: {
			'countries-true': 'collaborating with shcolars at',
			'countries-false': 'citing scholars working at'
		},
		authors: { 'countries-false': 'citing papers authored by' },
		sources: { 'countries-true': 'where authors publish in' },
		subfields: {}
	};

	function countrySemantify(rootType: tt.RootType, bd: string) {
		let oBase = C_SEM_MAP[rootType];
		if (oBase == undefined) return '';
		return oBase[bd] || '';
	}

	$: titleSuffix =
		selectedBreakdowns != undefined ? countrySemantify(conf.rootType, selectedBreakdowns[0]) : '';
</script>

<h3>Countries {titleSuffix} {rootName}</h3>

<span id="map-control-block">
	{#if Object.keys(levelOptions).length > 1}
		<select bind:value={selectedBreakdowns[0]} class="sel-base" aria-label="Breakdown selection">
			{#each Object.keys(levelOptions) as bd}
				<option value={bd}>
					{countrySemantify(conf.rootType, bd)}
				</option>
			{/each}
		</select>
	{/if}
	Since
	<select bind:value={year} aria-label="Since year"
		>{#each treeSpecs.yearBreaks as y}
			<option>{y}</option>
		{/each}
	</select>
	<input type="checkbox" bind:checked={isSpec} /> Specialization
</span>
<svg bind:this={svgEl} viewBox="{xMin} {yMin} {mapWidth} {mapHeight}">
	<!-- svelte-ignore a11y-mouse-events-have-key-events -->
	<!-- svelte-ignore a11y-click-events-have-key-events -->
	<!-- svelte-ignore a11y-no-noninteractive-element-interactions -->
	{#each Object.entries(countryPaths) as [cc, cpaths]}
		{#each cpaths as d}
			<path
				{d}
				stroke-width="1"
				stroke="black"
				class={classNamer(cc)}
				role="region"
				on:mouseover={setHover(cc)}
				on:click={() => {
					clicked = !clicked;
					setHover(cc)();
				}}
			/>
		{/each}
	{/each}
</svg>

<div id="map-label-container" style="--grad: {getGradient()}">
	<div>{formatNumber(minw || 0)}</div>
	<div class="label-gradient-box">
		{#if highlightedRate != undefined}<div
				id="w-tick"
				style="--loff: {highlightedRate * 100}%"
			/>{/if}
	</div>
	<div>{formatNumber(maxw || 0)}</div>
	<div id="w-text">{weightText}</div>
</div>

<div id="map-hover">
	{#if resp != undefined}
		<PathLevelInfoBox
			path={infoPath}
			rootNode={resp.tree}
			initHeight={120}
			{rootName}
			treeSpec={currentTreeSpec}
			{rootId}
			attributeLabels={resp.atts}
		/>
	{/if}
</div>

<style>
	h3 {
		text-align: center;
	}

	svg {
		max-height: 65svh;
	}

	path {
		fill: none;
		fill-opacity: 0;
		stroke: var(--color-text);
		transition: all 800ms;
	}

	.label-gradient-box {
		width: 80%;
		height: 16px;
		background: var(--grad);
	}

	#map-hover {
		position: relative;
		height: 160px;
		width: 100%;
	}

	#map-control-block {
		display: flex;
		gap: var(--unified-padding);
		justify-content: center;
		width: 100%;
		margin-bottom: var(--unified-padding);
	}

	#w-text {
		width: 100%;
		text-align: center;
	}

	#w-tick {
		height: 100%;
		width: 0.5%;
		background: var(--color-text);
		position: relative;
		left: var(--loff);
		z-index: 20;
	}

	#map-label-container {
		display: flex;
		gap: var(--unified-padding);
		justify-content: center;
		flex-wrap: wrap;
	}
</style>
