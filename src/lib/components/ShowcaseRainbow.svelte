<script lang="ts">
	import { LATEST_YEAR } from '$lib/constants';
	import type { ShowcaseHitPaper } from '$lib/types/showcase';
	import { formatNumber } from '$lib/text-format-util';
	import { htmlToText } from '$lib/utils/paper-helpers';

	export let papers: ShowcaseHitPaper[];

	const W = 360;
	const H = 150;
	const padL = 6;
	const padR = 12;
	const padT = 14;
	const padB = 16;
	const baseY = H - padB;

	// Each hit paper is an arc climbing from its publication year (left) to today (right), its height
	// set by citations — the same "rainbow of trajectories" the real PaperRainbow draws, in miniature.
	$: minYear = Math.min(LATEST_YEAR - 1, ...papers.map((p) => p.year));
	$: span = Math.max(1, LATEST_YEAR - minYear);
	$: rootMax = Math.sqrt(Math.max(1, ...papers.map((p) => p.citations)));
	// Tallest in back, so smaller arcs stay readable in front; hue spreads the spectrum across them.
	$: ordered = papers.map((p, i) => ({ ...p, i })).sort((a, b) => b.citations - a.citations);

	const xOf = (yr: number) => padL + ((yr - minYear) / span) * (W - padL - padR);
	const topOf = (cit: number) => padT + (1 - Math.sqrt(cit) / rootMax) * (baseY - padT);
	const hue = (i: number, n: number) => Math.round((i / Math.max(1, n - 1)) * 300);

	function arc(p: ShowcaseHitPaper): string {
		const x0 = xOf(p.year);
		const x1 = W - padR;
		const y1 = topOf(p.citations);
		return `M${x0} ${baseY} C${x0 + (x1 - x0) * 0.42} ${baseY} ${x0 + (x1 - x0) * 0.62} ${y1} ${x1} ${y1}`;
	}
	function area(p: ShowcaseHitPaper): string {
		return `${arc(p)} L${W - padR} ${baseY} L${xOf(p.year)} ${baseY} Z`;
	}
</script>

<div class="rainbow">
	<svg viewBox="0 0 {W} {H}" role="img" aria-label="Hit-paper citation rainbow">
		<line class="base" x1={padL} y1={baseY} x2={W - padR} y2={baseY} />
		{#each ordered as p, k (k)}
			{@const c = `hsl(${hue(p.i, ordered.length)} 68% 55%)`}
			<g>
				<title>{htmlToText(p.name)} ({p.year}) · {formatNumber(p.citations)} citations</title>
				<path class="fill" d={area(p)} fill={c} />
				<path class="line" d={arc(p)} stroke={c} />
				<circle cx={W - padR} cy={topOf(p.citations)} r="2.6" fill={c} />
			</g>
		{/each}
		<text class="yr" x={xOf(minYear)} y={H - 4} text-anchor="start">{minYear}</text>
		<text class="yr" x={W - padR} y={H - 4} text-anchor="end">today</text>
	</svg>
	<p class="cap">Each arc is a hit paper, climbing by citations from publication to today.</p>
</div>

<style>
	.rainbow {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	svg {
		width: 100%;
		height: auto;
		display: block;
		overflow: visible;
	}

	.base {
		stroke: rgba(var(--color-range-30), 0.3);
		stroke-width: 1;
	}

	.fill {
		opacity: 0.07;
	}

	.line {
		fill: none;
		stroke-width: 2;
		stroke-linecap: round;
		opacity: 0.9;
	}

	.yr {
		fill: var(--color-text);
		font-size: 9px;
		opacity: 0.45;
	}

	.cap {
		margin: 0;
		font-size: var(--text-xs);
		opacity: 0.55;
	}
</style>
