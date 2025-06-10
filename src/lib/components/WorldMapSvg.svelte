<script lang="ts">
	import { onMount } from 'svelte';

	import type * as tt from '$lib/tree-types';
	import * as tf from '$lib/tree-functions';

	import countryPaths from '$lib/assets/data/country-svg-paths.json';
	// import countryBoxes from '$lib/assets/data/country-svg-boxes.json';
	import { getColor, getColorArr } from '$lib/style-util';
	import { formatNumber, semantify } from '$lib/text-format-util';
	import { BE_REMOTE_URL, HIGH_OP, LOW_OP } from '$lib/constants';
	import PathLevelInfoBox from './PathLevelInfoBox.svelte';

	export let rootName = '';
	export let prefixText = '';
	export let countryL1Specs: number[];
	export let conf: tt.FullTreeConfig;
	export let treeSpecs: tt.TreeSpecs;
	export let resp: tt.TreeResponse | undefined;
	export let treeId = countryL1Specs[0];

	type LevelT = tt.OMap<{ w: number; id: number }>;

	let year = conf.year;
	let countryLevels: LevelT = {};
	let mounted = false;
	let highlighted = '';
	let highlightedRate: undefined | number;
	let infoPath: number[] = [];

	let baselineOp = ((LOW_OP + HIGH_OP) * 0.7) / 200;
	let colorRates = [0.5, 0.4, 0.3, 0.2, 0.1];
	let minColor = colorRates[0];
	let maxColor = colorRates[colorRates.length - 1];
	let xMin = 0;
	let yMin = 0;
	let mapWidth = 2000;
	let mapHeight = 1000;
	let maxw: undefined | number;
	let minw: undefined | number;
	let svgEl: SVGSVGElement;
	let styleEl: SVGStyleElement | null = null;
	const TOP_N = 15;

	let currentTreeSpec = treeSpecs.specs[conf.rootType][treeId];
	let selectedBreakdowns = tf.getDefaultBreakdowns(currentTreeSpec);
	let isSpec = currentTreeSpec.defaultIsSpec;
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
		const scaler = (w: number) => (((w - (minw || 0)) / wspan) * baselineOp) / 3 + baselineOp;
		const sLines = [];
		for (const [c, { w }] of Object.entries(levels)) {
			let colorR = ((w - (minw || 0)) / wspan) * (maxColor - minColor) + minColor;
			let lineColor = getColor(colorR);
			let isHighlighted = c == highlighted;
			let opa = scaler(w);
			if (isHighlighted) {
				opa = 1.9;
			}
			let line = `fill: ${lineColor}; fill-opacity: ${opa};`;
			if (isHighlighted) {
				line += `stroke: ${lineColor};stroke-width: 4.5;`;
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

	function updateStyle(styleEl: SVGStyleElement | null, l1Weights: LevelT, highlighted) {
		if (styleEl == undefined) return;
		styleEl.textContent = getClassStyles(l1Weights, highlighted);
	}
	function reloadResp(treeId: number, year: number) {
		if (mounted == false) return;
		let newConf: tt.FullTreeConfig = { ...conf, treeId, year };
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

	$: titleSuffix =
		selectedBreakdowns != undefined
			? semantify(selectedBreakdowns[0], conf.rootType, selectedBreakdowns, 0).split('<')[0]
			: '';

	onMount(() => {
		const svgNS = 'http://www.w3.org/2000/svg';
		styleEl = document.createElementNS(svgNS, 'style') as SVGStyleElement;
		svgEl.insertBefore(styleEl, svgEl.firstChild);
		mounted = true;
		if (resp == undefined) {
			reloadResp(treeId, year);
		}
	});

	let globConf: tt.FullControlSpecs;

	$: globConf = {
		globalSizeBase: isSpec ? 'specialization' : 'volume',
		globalLimit: TOP_N,
		levelSpecs: [tf.DEFAULT_CONTROL_SPEC]
	};
	$: visibleTreeInfo = getVisTree(resp, globConf);
	$: weightText = isSpec ? 'Revealed comparative advantage' : 'Citations';
	$: updateTreeId(selectedBreakdowns, levelOptions);
	$: updateL1(visibleTreeInfo);
	$: updateStyle(styleEl, countryLevels, highlighted);
	$: reloadResp(treeId, year);

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

	function getGradient(colorRates: number[]) {
		let steps = [];
		for (const [i, cr] of colorRates.entries()) {
			let pct = (100 * i) / (colorRates.length - 1);
			steps.push(`rgba(${getColorArr(cr)}, ${baselineOp}) ${pct}%`);
		}
		return `linear-gradient(to right, ${steps.join(', ')})`;
	}
</script>

<h2>{prefixText} {rootName} {titleSuffix} - top {TOP_N}</h2>

<span>
	<select bind:value={selectedBreakdowns[0]} class="sel-base" aria-label="Breakdown selection">
		{#each Object.keys(levelOptions) as bd}
			<option value={bd}>
				{semantify(bd, conf.rootType, selectedBreakdowns, 0)}
			</option>
		{/each}
	</select>
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

<div id="map-label-container" style="--grad: {getGradient(colorRates)}">
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
			rootId={resp.tree.topSourceId}
			attributeLabels={resp.atts}
		/>
	{/if}
</div>

<style>
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
