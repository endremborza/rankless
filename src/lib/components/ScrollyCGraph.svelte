<script lang="ts">
	import citeGraph from '$lib/assets/data/cgraph.json';
	import {formatNumber} from '$lib/text-format-util';

	export let scrollY: number;
	export let sHeight: number;
	export let isWideScreen: boolean;
	export let ratePin: (s: number, e: number, os: number) => number;

	function getPD(arr: number[]) {
		const o = [];
		for (const [i, e] of arr.entries()) {
			o.push(`${(i / arr.length).toFixed(3)} ${1 - e}`);
		}
		return 'M ' + o.join(' L ');
	}
	const norm = (x: number) => Math.max(0, Math.min(1, x));
	// második szám: sebesség
	//első szám: hol kezdi
	$: mainScaler = norm(((scrollY - sHeight * 0.5) / sHeight) * 1.2);
	$: subScaler = norm(((scrollY - sHeight * 1.6) / sHeight) * 2);

	$: line1 = citeGraph.citations.map((x) => x * mainScaler);

	// első szám hol kezd
	//második: meddig
	//harmadik: top margin
	$: topOffset = ratePin(1, 3, 0.08);

	let mainColor = 'rgb(var(--color-range-30))';
	let subColor = 'rgb(var(--color-range-75))';
	//let subColor = 'var(--color-theme-darkblue)';

	$: [mainLop, subLop] = [
		`${Math.pow(mainScaler, 0.5) * 100}%`,
		`${Math.pow(subScaler, 2) * 100}%`
	];

	let mainLegend = [
		[0.15, 'Total number of references'],
		[0.22, 'in published articles']
	];
	let subLegend = [
		[0.32, 'References to papers with the'],
		[0.39, 'same country of origin']
	];

	$: minVal = Math.min(...citeGraph.citations);
	$: minTick = 1 - minVal;
	$: [height, width] = isWideScreen ? ['90svh', '50%'] : ['45svh', '100%'];
</script>

<svg viewBox="-0.18 -0.25 1.34 1.4" {height} {width} style="top: {topOffset}px">
	<path d="{getPD(line1)}V1H0z" style="fill: {mainColor};" stroke-width="0.01" />
	<path d="{getPD(citeGraph.incite)}V1H0z" style="fill: {subColor};" stroke-width="0.01" opacity={subScaler} />
	<path d="M0,1v-1.2" style="stroke: var(--color-theme-darkgrey);" stroke-width="0.01" />
	<path d="M0,1h1" style="stroke: var(--color-theme-darkgrey);" stroke-width="0.01" />
	<g opacity={mainScaler}>
		<path d="M-0.02,{1 - mainScaler}h0.04" style="stroke: {mainColor};" stroke-width="0.01" />
		<text x="-0.03" y="{1.01 - mainScaler}" font-size="0.04" text-anchor="end">{formatNumber(citeGraph.maxval)}</text>
		<path d="M-0.02,{minTick}h0.04" style="stroke: {mainColor};" stroke-width="0.01" />
		<text x="-0.03" y={minTick} font-size="0.04" text-anchor="end">{formatNumber(minVal *
			citeGraph.maxval)}</text>
	</g>
	{#each [[mainLegend, mainColor, mainLop], [subLegend, subColor, subLop]] as [legend, color, opacity]}
	{#each legend as [y, line]}
	<text x="0.03" {y} font-size="0.054" text-anchor="start" style="fill: {color}; font-weight: 800"
		{opacity}>{line}</text>
	{/each}
	{/each}
	{#each citeGraph.year.entries() as [i, y]}
	{#if y % 5 == 0}
	<path d="M{i / citeGraph.year.length},1.03v-0.06" stroke-width="0.01"
		style="stroke: var(--color-theme-darkgrey);" />
	<text x={i / citeGraph.year.length} text-anchor="middle" y="1.1" font-size="0.06">{y}</text>
	{/if}
	{/each}
</svg>

<style>
	svg {
		position: absolute;
		left: 0px;
		z-index: 3;
	}
</style>
