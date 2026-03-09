<script lang="ts">
	import type { AuthorPeersResp, PeerAuthorEntry } from '$lib/tree-types';
	import { formatNumber } from '$lib/text-format-util';

	export let data: AuthorPeersResp;

	$: allEntries = [data.hero, ...data.peers];
	$: sfMax = data.topSubfields.map((_, si) =>
		Math.max(1, ...allEntries.map((e) => e.subfieldCitations[si] ?? 0))
	);

	function sfOpacity(val: number, max: number): number {
		if (max === 0) return 0;
		return 0.1 + 0.9 * (val / max);
	}

	function sparkMax(entries: PeerAuthorEntry[]): { papers: number; cites: number } {
		return {
			papers: Math.max(1, ...entries.flatMap((e) => e.yearlyPapers)),
			cites: Math.max(1, ...entries.flatMap((e) => e.yearlyCites))
		};
	}

	$: sMax = sparkMax(allEntries);

	const STOP = /^(and|of|the|in|for|a|an|at|by|to)$/i;

	function abbrSfName(name: string): string {
		const significant = name.split(/\s+/).filter((w) => !STOP.test(w));
		if (significant.length === 0) return name.slice(0, 5);
		if (significant.length === 1) return significant[0].slice(0, 5);
		return significant.map((w) => w[0]).join('');
	}

	let hoveredTooltip: number | null = null;
	let stuckTooltip: number | null = null;
	let tooltipX = 0;
	let tooltipY = 0;

	$: activeTooltip = stuckTooltip ?? hoveredTooltip;

	function setPos(el: Element) {
		const r = el.getBoundingClientRect();
		tooltipX = r.left + r.width / 2;
		tooltipY = r.top;
	}

	function onEnter(si: number, e: MouseEvent) {
		hoveredTooltip = si;
		if (stuckTooltip === null) setPos(e.currentTarget as HTMLElement);
	}

	function onLeave() {
		hoveredTooltip = null;
	}

	function onBtnClick(si: number, e: MouseEvent) {
		if (stuckTooltip === si) {
			stuckTooltip = null;
		} else {
			stuckTooltip = si;
			setPos(e.currentTarget as HTMLElement);
		}
	}
</script>

<svelte:window on:click={() => (stuckTooltip = null)} />

<div class="peers-table-wrap">
	<table class="peers-table">
		<thead>
			<tr>
				<th class="name-col">Author</th>
				{#each data.topSubfields as sf, si}
					<th
						class="sf-col"
						on:mouseenter={(e) => onEnter(si, e)}
						on:mouseleave={onLeave}
					>
						<button
							class="sf-header-btn"
							on:click|stopPropagation={(e) => onBtnClick(si, e)}
						>{abbrSfName(sf.name)}</button>
					</th>
				{/each}
				<th class="spark-col">Last Decade</th>
				<th class="stat-col">Papers</th>
				<th class="stat-col">Cites</th>
			</tr>
		</thead>
		<tbody>
			{#each allEntries as entry, ei}
				{@const isHero = ei === 0}
				<tr class:hero-row={isHero}>
					<td class="name-cell">
						{#if isHero}
							<strong>{entry.name}</strong>
						{:else}
							<a href="/authors/{entry.semanticId}">{entry.name}</a>
						{/if}
					</td>
					{#each data.topSubfields as _, si}
						{@const val = entry.subfieldCitations[si] ?? 0}
						<td
							class="sf-cell"
							style="--sf-opacity: {sfOpacity(val, sfMax[si])}"
						>
							{val > 0 ? val : ''}
						</td>
					{/each}
					<td class="spark-cell">
						<svg viewBox="0 0 {entry.yearlyPapers.length} 2" class="sparkline" preserveAspectRatio="none">
							{#each entry.yearlyCites as c, i}
								<rect x={i} y={0} width={0.8} height={c / sMax.cites} class="cite-bar" />
							{/each}
							{#each entry.yearlyPapers as p, i}
								<rect x={i} y={1} width={0.8} height={p / sMax.papers} class="paper-bar" />
							{/each}
							<line x1={0} x2={entry.yearlyPapers.length} y1={1} y2={1} class="axis" />
						</svg>
					</td>
					<td class="stat-cell">{formatNumber(entry.papers)}</td>
					<td class="stat-cell">{formatNumber(entry.citations)}</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>

{#if activeTooltip !== null}
	<div
		class="sf-tooltip"
		style="left:{tooltipX}px; top:{tooltipY}px;"
	>
		{data.topSubfields[activeTooltip].name}
	</div>
{/if}

<style>
	.peers-table-wrap {
		overflow-x: auto;
	}

	.peers-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.78rem;
	}

	thead th {
		font-size: 0.65rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		opacity: 0.6;
		padding: 4px 6px;
		white-space: nowrap;
		text-align: center;
		border-bottom: 1px solid rgba(var(--color-range-15), 0.15);
	}

	.sf-header-btn {
		background: none;
		border: none;
		padding: 0;
		font: inherit;
		color: inherit;
		cursor: pointer;
		text-transform: inherit;
		letter-spacing: inherit;
	}

	.sf-header-btn:hover {
		opacity: 0.8;
	}

	.sf-tooltip {
		position: fixed;
		transform: translateX(-50%) translateY(calc(-100% - 6px));
		background: #222;
		color: #fff;
		padding: 6px 10px;
		border-radius: 4px;
		font-size: 0.82rem;
		white-space: nowrap;
		z-index: 100;
		pointer-events: none;
		text-transform: none;
		letter-spacing: 0;
	}

	.name-col {
		text-align: left !important;
	}

	tbody tr {
		border-bottom: 1px solid rgba(var(--color-range-15), 0.06);
	}

	.hero-row {
		background: rgba(var(--color-range-15), 0.04);
	}

	td {
		padding: 5px 6px;
	}

	.name-cell {
		white-space: nowrap;
	}

	.name-cell a {
		color: inherit;
		text-decoration: none;
	}

	.name-cell a:hover {
		text-decoration: underline;
	}

	.sf-cell {
		text-align: center;
		font-size: 0.75rem;
		font-variant-numeric: tabular-nums;
		background: rgba(var(--color-range-15), var(--sf-opacity, 0));
		border-radius: 2px;
	}

	.spark-cell {
		padding: 2px 4px;
		min-width: 80px;
	}

	.sparkline {
		width: 100%;
		height: 28px;
		display: block;
	}

	.cite-bar {
		fill: rgba(var(--color-range-15), 0.35);
	}

	.paper-bar {
		fill: rgba(var(--color-range-15), 0.12);
	}

	.axis {
		stroke: rgba(var(--color-range-15), 0.15);
		stroke-width: 0.04;
	}

	.stat-cell {
		text-align: right;
		font-variant-numeric: tabular-nums;
		font-size: 0.75rem;
		opacity: 0.7;
	}

	@media (min-width: 1200px) {
		.peers-table {
			font-size: 0.95rem;
		}

		thead th {
			font-size: 0.8rem;
			padding: 6px 10px;
		}

		td {
			padding: 7px 10px;
		}

		.sf-cell,
		.stat-cell {
			font-size: 0.9rem;
		}

		.spark-cell {
			min-width: 120px;
		}

		.sparkline {
			height: 36px;
		}
	}
</style>
