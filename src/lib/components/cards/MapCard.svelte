<script lang="ts">
	import countryPaths from '$lib/assets/data/country-svg-paths.json';
	import { INK, INNER, MONO, MUTED, PAPER, SANS, HAIRLINE } from '$lib/utils/cards';
	import { LEGEND_SWATCH, LEGEND_TEXT, type MapCardProps } from '$lib/utils/flat-out-cards';
	import CardLabels from './CardLabels.svelte';

	export let transform: MapCardProps['transform'];
	export let shades: MapCardProps['shades'];
	export let hl: MapCardProps['hl'];
	export let strokes: MapCardProps['strokes'];
	export let labels: MapCardProps['labels'];
	export let legend: MapCardProps['legend'];

	const NO_DATA = '#eee';
	const paths = Object.entries(countryPaths as Record<string, string[]>);
	$: hlPaths = paths.filter(([name]) => hl.includes(name));
</script>

<svg viewBox="0 0 {INNER.w} {INNER.h}" xmlns="http://www.w3.org/2000/svg">
	<g {transform} stroke={PAPER} stroke-width={strokes.border} stroke-linejoin="round">
		{#each paths as [name, ds] (name)}
			{#each ds as d, i (i)}
				<path {d} fill={shades[name]?.fill ?? NO_DATA} fill-opacity={shades[name]?.opacity ?? 1} />
			{/each}
		{/each}
		{#each hlPaths as [name, ds] (name)}
			{#each ds as d, i (i)}
				<path {d} fill="none" stroke={INK} stroke-width={strokes.hl} />
			{/each}
		{/each}
	</g>
	<CardLabels {labels} dots />
	<g font-size={LEGEND_TEXT}>
		<text x="0" y={legend.y} font-family={SANS} fill={INK}>{legend.title}</text>
		{#each legend.rows as row, i (i)}
			<rect
				x="0"
				y={row.y}
				width={LEGEND_SWATCH.w}
				height={LEGEND_SWATCH.h}
				fill={row.fill}
				fill-opacity={row.opacity}
				stroke={HAIRLINE}
			/>
			<text
				x={LEGEND_SWATCH.w + LEGEND_SWATCH.gap}
				y={row.y + LEGEND_SWATCH.h - 3}
				font-family={MONO}
				fill={MUTED}>{row.text}</text
			>
		{/each}
	</g>
</svg>
