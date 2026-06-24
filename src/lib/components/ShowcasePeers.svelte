<script lang="ts">
	import type { ShowcasePeers } from '$lib/types/showcase';
	import { abbrSfName, sfColorVar } from '$lib/peers-utils';
	import { formatNumber } from '$lib/text-format-util';
	import BarChart, { type Bar } from '$lib/components/BarChart.svelte';

	export let data: ShowcasePeers;

	const PLOT_H = 150;
	const YEAR_COLOR = '--color-range-40';

	$: fieldMax = Math.max(1, ...data.subfields.map((s) => s.cites));
	$: fieldBars = data.subfields.map(
		(s, k): Bar => ({
			height: (s.cites / fieldMax) * 100,
			colorVar: sfColorVar(k),
			axisLabel: abbrSfName(s.name),
			tip: `${s.name}\n${formatNumber(s.cites)} citations`
		})
	);

	$: years = data.yearly.map((_, i) => data.yearFrom + i);
	$: yearMax = Math.max(1, ...data.yearly);
	$: yearBars = data.yearly.map(
		(c, i): Bar => ({
			height: (c / yearMax) * 100,
			colorVar: YEAR_COLOR,
			axisLabel: i === 0 || i === data.yearly.length - 1 ? String(years[i]) : '',
			tip: `${years[i]}\n${formatNumber(c)} citations`
		})
	);
</script>

<div class="peers-preview">
	<div class="col">
		<div class="col-title">Citations by field</div>
		<BarChart bars={fieldBars} plotHeight={PLOT_H} gap={8} />
	</div>
	<div class="col">
		<div class="col-title">Citations by year</div>
		<BarChart bars={yearBars} plotHeight={PLOT_H} gap={4} />
	</div>
</div>

<style>
	.peers-preview {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 20px;
		align-items: end;
	}

	.col {
		display: flex;
		flex-direction: column;
		gap: 10px;
		min-width: 0;
		/* room under the plot for the rotated/short axis labels */
		padding-bottom: 18px;
	}

	.col-title {
		font-size: var(--text-xs);
		text-transform: uppercase;
		letter-spacing: 0.04em;
		opacity: 0.55;
	}

	@media (max-width: 540px) {
		.peers-preview {
			grid-template-columns: 1fr;
			gap: 24px;
		}
	}
</style>
