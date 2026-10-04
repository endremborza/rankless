<script lang="ts">
	import { FAINT, INK, INNER, MONO, MUTED, PAPER, SANS } from '$lib/utils/cards';
	import { FIELDS_PLOT_W, LEGEND_TEXT, type FieldsCardProps } from '$lib/utils/flat-out-cards';
	import CardLabels from './CardLabels.svelte';

	export let nodes: FieldsCardProps['nodes'];
	export let edges: FieldsCardProps['edges'];
	export let labels: FieldsCardProps['labels'];
	export let domains: FieldsCardProps['domains'];
	export let sizeText: FieldsCardProps['sizeText'];

	const LEGEND_X = FIELDS_PLOT_W + 40;
	const ROW = 32;
	const LEGEND_Y = (INNER.h - ROW * 6.3) / 2;
	const KEY_R = [4, 7, 10];
</script>

<svg viewBox="0 0 {INNER.w} {INNER.h}" xmlns="http://www.w3.org/2000/svg">
	<g stroke={FAINT} stroke-opacity="0.45" stroke-width="0.6">
		{#each edges as [x1, y1, x2, y2], i (i)}
			<line {x1} {y1} {x2} {y2} />
		{/each}
	</g>
	{#each nodes as n, i (i)}
		<circle cx={n.x} cy={n.y} r={n.r} fill={n.fill} stroke={n.fill} stroke-width="0.9" />
		<circle cx={n.x} cy={n.y} r={n.r * 0.9} fill={PAPER} fill-opacity={n.sat} />
		{#if n.hl}
			<circle cx={n.x} cy={n.y} r={n.r + 2} fill="none" stroke={INK} stroke-width="2.5" />
		{/if}
	{/each}
	<CardLabels {labels} />
	<g font-family={SANS} font-size={LEGEND_TEXT + 1} fill={INK}>
		{#each domains as d, i (i)}
			<circle cx={LEGEND_X + 9} cy={LEGEND_Y + i * ROW} r="9" fill={d.fill} />
			<text x={LEGEND_X + 28} y={LEGEND_Y + i * ROW + 5.5}>{d.name}</text>
		{/each}
		{#each KEY_R as r, i (i)}
			<circle
				cx={LEGEND_X + 9 + i * 26}
				cy={LEGEND_Y + 4.7 * ROW}
				{r}
				fill={FAINT}
				fill-opacity={0.3 + i * 0.3}
			/>
		{/each}
		<text x={LEGEND_X} y={LEGEND_Y + 5.6 * ROW} fill={MUTED}>Larger, deeper circles:</text>
		<text x={LEGEND_X} y={LEGEND_Y + 6.3 * ROW}>{sizeText}</text>
	</g>
</svg>
