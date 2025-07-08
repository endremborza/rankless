<script lang="ts">
	import { onMount } from 'svelte';

	import type * as tt from '$lib/tree-types';
	import * as tf from '$lib/tree-functions';

	import countryPaths from '$lib/assets/data/country-svg-paths.json';
	// import countryBoxes from '$lib/assets/data/country-svg-boxes.json';
	import { getColor, getColorArr } from '$lib/style-util';
	import { formatNumber } from '$lib/text-format-util';
	import { HIGH_OP, LOW_OP } from '$lib/constants';
	import FlatOutFrame from './FlatOutFrame.svelte';

	export let rootName = '';
	export let rootId: number;
	export let indsByEntityType: tt.IndsByEntityType;
	export let conf: tt.FullTreeConfig;
	export let treeSpecs: tt.TreeSpecs;

	let resp: tt.TreeResponse | undefined;
	let countryLevels: tt.LevelT = {};
	let highlighted = '';
	let highlightedRate: undefined | number;
	let highlightedQ = -1;
	let infoPath: number[] = [];

	let minOp = LOW_OP * 0.65;
	let maxOp = HIGH_OP * 1.2;
	let minColorRate = 0.32;
	let maxColorRate = 0.45;

	let xMin = 0;
	let yMin = -20;
	let mapWidth = 2000;
	let mapHeight = 950;
	let maxw = 0;
	let minw = 0;
	let svgEl: SVGSVGElement;
	let styleEl: SVGStyleElement | null = null;

	let nBreakPoints = 3;
	let pullerRate = 0.12;
	let breakPoints: number[] = [];

	let clicked = false;
	let isSpec = false;
	let treeId: number;
	let flatOut = {};

	$: isRefSide = treeSpecs.specs[conf.rootType][treeId]?.breakdowns[0].sourceSide;
	$: weightText = isSpec
		? 'Revealed comparative advantage'
		: isRefSide
		? 'Total citations of papers'
		: 'Citations';
	$: updateL1(flatOut, resp);
	$: updateStyle(styleEl, countryLevels, highlighted, highlightedQ, nBreakPoints, pullerRate);

	const fixNameForPaths = (s: string) => (s == 'Türkiye' ? 'Turkey' : s);
	const fixNameForData = (s: string) => (s == 'Turkey' ? 'Türkiye' : s);
	const getColorRate = (r: number) => r * (maxColorRate - minColorRate) + minColorRate;
	const getOpaRate = (r: number) => r * (maxOp - minOp) + minOp;

	function classNamer(s: string) {
		let sn = fixNameForPaths(s);
		return `country-${sn.toLowerCase().replaceAll(' ', '-')}`;
	}

	function getClassStyles(
		levels: tt.LevelT,
		highlighted: string,
		highlightedQ: number,
		nBreakPoints: number,
		pullerRate: number
	) {
		if (Object.values(levels).length == 0) return '';
		const { linScaler, newBreakPoints, locMinw, locMaxw } = tf.getFlatRescaler(
			levels,
			nBreakPoints,
			pullerRate
		);
		let scaler = (w: number) => {
			return { op: getOpaRate(linScaler(w)), hl: false, color: getColorRate(linScaler(w)) };
		};
		if (nBreakPoints > 0) {
			scaler = (w: number) => {
				let oI = 0;
				for (let i = 1; i <= nBreakPoints; i++) {
					if (w >= newBreakPoints[i]) oI++;
				}
				let color = getColorRate(oI / nBreakPoints);
				return { op: getOpaRate(oI / nBreakPoints), hl: oI == highlightedQ, color };
			};
		}
		const sLines = [];
		for (const [c, { w }] of Object.entries(levels)) {
			let isHighlighted = c == highlighted;
			let { op, hl, color } = scaler(w);
			let lineColor = getColor(color);
			isHighlighted = isHighlighted || hl;
			let line = `fill: ${lineColor}; fill-opacity: ${op / 100};`;
			if (isHighlighted) {
				line += `stroke-width: 4.5;`;
			}
			sLines.push(`path.${classNamer(c)} {${line}}`);
		}
		[minw, maxw, breakPoints] = [locMinw || 0, locMaxw || 1, newBreakPoints];
		return sLines.join('\n');
	}

	function updateL1(flatOut: undefined | tt.LevelT, resp: undefined | tt.TreeResponse) {
		if (flatOut != undefined && resp != undefined) {
			try {
				let l1Kv = Object.entries(flatOut).map(([k, { w }]) => [
					resp.atts['countries'][k].name,
					{ w, id: k }
				]);
				countryLevels = Object.fromEntries(l1Kv);
			} catch (error) {
				console.log(error);
			}
		}
	}

	function updateStyle(
		styleEl: SVGStyleElement | null,
		l1Weights: tt.LevelT,
		highlighted: string,
		highlightedQ: number,
		nbps: number,
		pullerRate: number
	) {
		if (styleEl == undefined) return;
		styleEl.textContent = getClassStyles(l1Weights, highlighted, highlightedQ, nbps, pullerRate);
	}

	function setHover(cc: string) {
		return () => {
			if (!clicked) {
				highlighted = fixNameForData(cc);
				if (highlighted in countryLevels && highlighted != '') {
					infoPath = [countryLevels[highlighted].id];
					if (maxw != undefined && minw != undefined) {
						highlightedRate = (countryLevels[highlighted].w - minw) / (maxw - minw);
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
			`rgba(${getColorArr(minColorRate)}, ${minOp}%) 0%`,
			`rgba(${getColorArr(maxColorRate)}, ${maxOp}%) 100%`
		];
		// for (const [i, cr] of colorRates.entries()) {
		// 	let pct = (100 * i) / (colorRates.length - 1);
		// 	steps.push(`rgba(${getColorArr(cr)}, ${baselineOp}) ${pct}%`);
		// }
		return `linear-gradient(to right, ${steps.join(', ')})`;
	}

	function bpEnd(bps: number[], i: number) {
		let nBp = bps[i + 1] - 1 || maxw || 0;
		if (nBp < bps[i]) {
			return nBp + 1;
		}
		return nBp;
	}

	onMount(() => {
		const svgNS = 'http://www.w3.org/2000/svg';
		styleEl = document.createElementNS(svgNS, 'style') as SVGStyleElement;
		svgEl.insertBefore(styleEl, svgEl.firstChild);
	});

	const C_SEM_MAP: Record<tt.RootType, Record<string, string>> = {
		countries: {
			'countries-true': 'collaborating with authors based in',
			'countries-false': 'citing scholars based in'
		},
		institutions: {
			'countries-true': 'collaborating with scholars at',
			'countries-false': 'citing scholars working at'
		},
		authors: { 'countries-false': 'citing papers authored by' },
		sources: { 'countries-true': 'where authors publish in' },
		subfields: {
			'countries-true': 'where authors publish papers about',
			'countries-false': 'where authors cite papers about'
		},
		'hit-papers': { 'countries-false': 'where authors are citing' }
	};

	function countrySemantify(rootType: tt.RootType, bd: string) {
		let oBase = C_SEM_MAP[rootType];
		if (oBase == undefined) return '';
		return oBase[bd] || '';
	}
</script>

<FlatOutFrame
	titlePrefix="Countries"
	l1Type="countries"
	semantifyer={countrySemantify}
	{rootName}
	{rootId}
	{indsByEntityType}
	{conf}
	{treeSpecs}
	year={treeSpecs.yearBreaks[0]}
	bind:flatOut
	bind:treeId
	bind:resp
	{infoPath}
>
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
					on:mouseleave={setHover('')}
					on:click={() => {
						clicked = !clicked;
						setHover(cc)();
					}}
				/>
			{/each}
		{/each}
	</svg>

	<div id="map-label-container" style="--grad: {getGradient()}">
		{#if nBreakPoints > 0}
			<!-- svelte-ignore a11y-mouse-events-have-key-events -->
			<div class="label-bp-container">
				{#each breakPoints as bp, i}
					<div
						class="label-bp-box"
						style="background-color: rgba({getColorArr(
							getColorRate(i / nBreakPoints)
						)}, {getOpaRate(i / nBreakPoints) / 100}); color: {getOpaRate(i / nBreakPoints) < 50
							? 'var(--color-text)'
							: 'var(--color-theme-white)'}"
						role="region"
						on:mouseover={() => {
							highlightedQ = i;
						}}
						on:mouseleave={() => {
							highlightedQ = -1;
						}}
					>
						<span>{formatNumber(bp)}</span> <span>-</span>
						<span>{formatNumber(bpEnd(breakPoints, i))}</span>
					</div>
				{/each}
			</div>
		{:else}
			<div>{formatNumber(minw || 0)}</div>
			<div class="label-gradient-box">
				{#if highlightedRate != undefined}<div
						id="w-tick"
						style="--loff: {highlightedRate * 100}%"
					/>{/if}
			</div>
			<div>{formatNumber(maxw || 0)}</div>
		{/if}
		<div id="w-text">{weightText}</div>
	</div>
</FlatOutFrame>

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

	.label-bp-box {
		flex: 1;
		max-width: 120px;
		display: flex;
		justify-content: space-evenly;
		padding: 4px;
		font-weight: 600;
		font-size: 12px;
		cursor: default;
	}

	.label-bp-container {
		width: 100%;
		display: flex;
		flex-wrap: wrap;
		justify-content: center;
		gap: var(--unified-padding);
	}

	.label-gradient-box {
		width: 80%;
		height: 16px;
		background: var(--grad);
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
