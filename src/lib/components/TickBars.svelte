<script lang="ts">
	export let h: number;
	export let iMul: number;
	export let nums: number[];
	export let color: string;
	export let scaleMax: number;
	export let flip: boolean = false;
	export let barW: number = iMul * 0.58;
	export let hovered: number | null = null;

	$: mult = flip ? -1 : 1;
</script>

<g class:dimmed={hovered != null}>
	{#each nums as v, i (i)}
		{#if v > 0}
			<line
				class="bar"
				class:hl={hovered === i}
				x1={i * iMul}
				x2={i * iMul}
				y1={0}
				y2={mult * (v / scaleMax) * h}
				stroke-width={barW}
				stroke={color}
			/>
		{/if}
	{/each}
</g>

<style>
	/* Opacity via class (not inline) so dark mode can lift faint pastels off the dark background, and
	   hovering one column can dim the rest. */
	.bar {
		opacity: 0.3;
		pointer-events: none;
	}

	.dimmed .bar {
		opacity: 0.12;
	}

	.dimmed .bar.hl {
		opacity: 0.96;
	}

	@media (prefers-color-scheme: dark) {
		.bar {
			opacity: 0.62;
		}

		.dimmed .bar {
			opacity: 0.26;
		}

		.dimmed .bar.hl {
			opacity: 0.97;
		}
	}
</style>
