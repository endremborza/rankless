<script lang="ts">
	import type { ShowcasePeers } from '$lib/types/showcase';
	import { abbrSfName } from '$lib/peers-utils';
	import { formatNumber } from '$lib/text-format-util';

	export let data: ShowcasePeers;

	const PLOT_H = 150;

	$: fieldMax = Math.max(1, ...data.subfields.flatMap((s) => [s.hero, s.peer]));
	$: years = data.heroYearly.map((_, i) => data.yearFrom + i);
	$: yearMax = Math.max(1, ...data.heroYearly, ...data.peerYearly);

	const pct = (v: number, max: number) => (v / max) * 100;
	const tip = (label: string, hero: number, peer: number) =>
		`${label}\n${data.heroName}: ${formatNumber(hero)}\n${data.peerName}: ${formatNumber(peer)}`;
</script>

<div class="peers-preview">
	<div class="legend">
		<span class="who"><i class="dot hero"></i>{data.heroName}</span>
		<span class="vs">vs</span>
		<span class="who"
			><i class="dot peer"></i>{data.peerName}{#if data.peerCountry}
				<span class="ctry">{data.peerCountry}</span>{/if}</span
		>
	</div>

	<div class="cols">
		<div class="col">
			<div class="col-title">Citations by field</div>
			<div class="bars" style="height:{PLOT_H}px">
				{#each data.subfields as sf, k (k)}
					<div class="grp" title={tip(sf.name, sf.hero, sf.peer)}>
						<div class="pair">
							<div class="bar hero" style="height:{pct(sf.hero, fieldMax)}%"></div>
							<div class="bar peer" style="height:{pct(sf.peer, fieldMax)}%"></div>
						</div>
						<span class="lbl">{abbrSfName(sf.name)}</span>
					</div>
				{/each}
			</div>
		</div>

		<div class="col">
			<div class="col-title">Citations by year</div>
			<div class="bars" style="height:{PLOT_H}px">
				{#each years as yr, i (i)}
					<div class="grp" title={tip(String(yr), data.heroYearly[i], data.peerYearly[i])}>
						<div class="pair tight">
							<div class="bar hero" style="height:{pct(data.heroYearly[i], yearMax)}%"></div>
							<div class="bar peer" style="height:{pct(data.peerYearly[i], yearMax)}%"></div>
						</div>
						<span class="lbl">{i === 0 || i === years.length - 1 ? yr : ''}</span>
					</div>
				{/each}
			</div>
		</div>
	</div>
</div>

<style>
	.peers-preview {
		display: flex;
		flex-direction: column;
		gap: 14px;
	}

	.legend {
		display: flex;
		align-items: center;
		gap: 10px;
		flex-wrap: wrap;
		font-size: var(--text-sm);
		font-weight: 600;
	}

	.who {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		min-width: 0;
	}

	.dot {
		width: 11px;
		height: 11px;
		border-radius: 2px;
		flex-shrink: 0;
	}

	.dot.hero {
		background: rgb(var(--color-range-40));
	}

	.dot.peer {
		background: rgb(var(--color-range-15));
	}

	.vs {
		opacity: 0.45;
		font-weight: 400;
	}

	.ctry {
		font-weight: 400;
		opacity: 0.55;
		margin-left: 4px;
	}

	.cols {
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
		padding-bottom: 18px;
	}

	.col-title {
		font-size: var(--text-xs);
		text-transform: uppercase;
		letter-spacing: 0.04em;
		opacity: 0.55;
	}

	.bars {
		display: flex;
		align-items: flex-end;
		gap: 8px;
	}

	.grp {
		position: relative;
		flex: 1;
		min-width: 0;
		height: 100%;
		display: flex;
		align-items: flex-end;
		justify-content: center;
	}

	.pair {
		display: flex;
		align-items: flex-end;
		justify-content: center;
		gap: 2px;
		width: 100%;
		height: 100%;
	}

	.pair.tight {
		gap: 1px;
	}

	.bar {
		flex: 1;
		min-width: 0;
		min-height: 1px;
		transition: filter 0.12s;
	}

	.bar.hero {
		background: rgb(var(--color-range-40));
	}

	.bar.peer {
		background: rgb(var(--color-range-15));
	}

	.grp:hover .bar {
		filter: brightness(1.12);
	}

	.lbl {
		position: absolute;
		bottom: -17px;
		left: 0;
		right: 0;
		text-align: center;
		font-size: var(--text-xs);
		font-weight: 600;
		letter-spacing: 0.02em;
		opacity: 0.6;
		white-space: nowrap;
	}

	@media (max-width: 540px) {
		.cols {
			grid-template-columns: 1fr;
			gap: 24px;
		}
	}
</style>
