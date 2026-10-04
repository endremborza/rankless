<script lang="ts">
	import { HAIRLINE, MONO, MUTED } from '$lib/utils/cards';

	// Dashed gridlines from `x1` to `x2`, each labelled `gap` left of `x1`.
	export let lines: { y: number; label: string }[];
	export let x1: number;
	export let x2: number;
	export let size: number;
	export let gap: number;
</script>

<g font-family={MONO} font-size={size}>
	{#each lines as g, i (i)}
		<line {x1} {x2} y1={g.y} y2={g.y} stroke={HAIRLINE} stroke-dasharray="4 4" />
		<text x={x1 - gap} y={g.y + size * 0.35} text-anchor="end" fill={MUTED}>{g.label}</text>
	{/each}
</g>
