<script lang="ts">
	import { onMount } from 'svelte';

	import countryPaths from '$lib/assets/data/country-svg-paths.json';
	import countryBoxes from '$lib/assets/data/country-svg-boxes.json';
	import { getColor } from '$lib/style-util';
	import { formatNumber } from '$lib/text-format-util';
	import { HIGH_OP, LOW_OP } from '$lib/constants';

	export let countryLevels: Record<string, number> = {};
	export let weightText: string = 'citations';

	let colorRates = [0.5, 0.4, 0.3, 0.2, 0.1, 0];
	let minColor = 0.5;
	let maxColor = 0.0;
	let maxw: undefined | number;
	let minw: undefined | number;

	function classNamer(s: string) {
		return `country-${s.toLowerCase().replaceAll(' ', '-')}`;
	}

	function getClassStyles(levels: Record<string, number>) {
		maxw = undefined;
		minw = undefined;
		for (const w of Object.values(levels)) {
			if (maxw == undefined || w > maxw) {
				maxw = w;
			}
			if (minw == undefined || w < minw) {
				minw = w;
			}
		}
		let wspan = (maxw || 1) - (minw || 0);
		const scaler = (w: number) => ((w - (minw || 0)) / wspan) * (HIGH_OP - LOW_OP) + LOW_OP;
		const sLines = [];
		for (const [c, w] of Object.entries(levels)) {
			let colorR = ((w - (minw || 0)) / wspan) * (maxColor - minColor) + minColor;
			let lineColor = getColor(colorR);
			sLines.push(`path.${classNamer(c)} {fill: ${lineColor}; fill-opacity: ${scaler(w)}}`);
		}
		return sLines.join('\n');
	}

	let xMin = 0;
	let yMin = 0;
	let mapWidth = 2000;
	let mapHeight = 1000;

	let svgEl: SVGSVGElement;
	let styleEl: SVGStyleElement | null = null;

	$: {
		if (styleEl) {
			styleEl.textContent = getClassStyles(countryLevels);
		}
	}

	onMount(() => {
		const svgNS = 'http://www.w3.org/2000/svg';
		styleEl = document.createElementNS(svgNS, 'style') as SVGStyleElement;
		svgEl.insertBefore(styleEl, svgEl.firstChild);
	});
	$: labelY = mapHeight * 0.935;
	$: fontSize = mapHeight * 0.04;
</script>

<svg bind:this={svgEl} viewBox="{xMin} {yMin} {mapWidth} {mapHeight}">
	<defs>
		<linearGradient id="fourColorGradient" x1="0%" y1="0%" x2="100%" y2="0%">
			{#each colorRates as colorRate, i}
				<stop offset="{(100 * i) / (colorRates.length - 1)}%" stop-color={getColor(colorRate)} />
			{/each}
		</linearGradient>
	</defs>

	{#each Object.entries(countryPaths) as [cc, cpaths]}
		{#each cpaths as d}
			<path {d} stroke-width="1" stroke="black" class={classNamer(cc)} />
		{/each}
	{/each}

	<rect
		x={mapWidth * 0.1}
		y={mapHeight * 0.9}
		width={mapWidth * 0.8}
		height={fontSize * 1.1}
		fill="url(#fourColorGradient)"
		fill-opacity={HIGH_OP / 100}
	/>
	<text x={mapWidth * 0.09} y={labelY} text-anchor="end" font-size={fontSize}
		>{formatNumber(minw || 0)}</text
	>
	<text x={mapWidth * 0.91} y={labelY} text-anchor="start" font-size={fontSize}
		>{formatNumber(maxw || 0)}</text
	>
	<text x={mapWidth / 2} y={labelY + fontSize * 1.2} text-anchor="middle" font-size={fontSize}
		>{weightText}</text
	>
</svg>

<style>
	path {
		fill: none;
		stroke: var(--color-text);
		transition: all 800ms;
	}
</style>
