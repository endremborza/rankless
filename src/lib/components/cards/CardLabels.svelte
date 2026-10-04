<script lang="ts">
	import { INK, MONO, MUTED, PAPER, SANS } from '$lib/utils/cards';
	import { LABEL_TEXT, VALUE_GAP, VALUE_TEXT, type CardLabel } from '$lib/utils/flat-out-cards';

	// The placed names with their values, haloed against the picture; with `dots`, a label moved
	// off its mark gets a dot on the mark.
	export let labels: CardLabel[];
	export let dots = false;
</script>

<g stroke={PAPER} stroke-width="3.5" stroke-linejoin="round" paint-order="stroke">
	{#each labels as l, i (i)}
		{#if dots && l.offset && !l.hl}
			<circle cx={l.anchor.x} cy={l.anchor.y} r="3" fill={INK} stroke-width="1.5" />
		{/if}
		<text
			x={l.tx}
			y={l.ty}
			text-anchor={l.align}
			font-family={SANS}
			font-size={LABEL_TEXT}
			fill={INK}
			>{l.name}<tspan dx={VALUE_GAP} font-family={MONO} font-size={VALUE_TEXT} fill={MUTED}
				>{l.value}</tspan
			></text
		>
	{/each}
</g>
