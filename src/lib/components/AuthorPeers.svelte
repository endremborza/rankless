<script lang="ts">
	import type { AuthorPeersResp, PeerAuthorEntry } from '$lib/tree-types';
	import { formatNumber } from '$lib/text-format-util';

	export let data: AuthorPeersResp;

	$: allEntries = [data.hero, ...data.peers];
	$: sfMax = data.topSubfields.map((_, si) =>
		Math.max(1, ...allEntries.map((e) => e.subfieldCitations[si] ?? 0))
	);
	$: heroSfCites = data.topSubfields.map((_, si) => data.hero.subfieldCitations[si] ?? 0);
	$: citesMax = Math.max(1, ...allEntries.flatMap((e) => e.yearlyCites));

	function sfOpacity(val: number, max: number): number {
		if (max === 0) return 0;
		return 0.1 + 0.9 * (val / max);
	}

	const STOP = /^(and|of|the|in|for|a|an|at|by|to)$/i;

	function abbrSfName(name: string): string {
		const significant = name.split(/\s+/).filter((w) => !STOP.test(w));
		if (significant.length === 0) return name.slice(0, 5);
		if (significant.length === 1) return significant[0].slice(0, 5);
		return significant.map((w) => w[0]).join('');
	}

	function sparkLinePath(vals: number[], max: number): string {
		if (!vals.length || max === 0) return '';
		return vals.map((v, i) => `${i === 0 ? 'M' : 'L'} ${i} ${(1 - v / max).toFixed(3)}`).join(' ');
	}

	function sparkAreaPath(vals: number[], max: number): string {
		if (!vals.length || max === 0) return '';
		const line = vals
			.map((v, i) => `${i === 0 ? 'M' : 'L'} ${i} ${(1 - v / max).toFixed(3)}`)
			.join(' ');
		return `${line} L ${vals.length - 1} 1 L 0 1 Z`;
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

<p class="peers-note">
	Peers are selected by citation overlap in the author's most active subfields.
	<span class="legend">
		<span class="leg-cite" /> citations ·
		<span class="leg-hero-ref" /> hero ref
	</span>
</p>
<div class="peers-table-wrap">
	<table class="peers-table">
		<thead>
			<tr>
				<th class="name-col">Author</th>
				{#each data.topSubfields as sf, si}
					<th class="sf-col" on:mouseenter={(e) => onEnter(si, e)} on:mouseleave={onLeave}>
						<button class="sf-header-btn" on:click|stopPropagation={(e) => onBtnClick(si, e)}
							>{abbrSfName(sf.name)}</button
						>
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
						{@const heroVal = heroSfCites[si]}
						<td class="sf-cell" style="--sf-opacity: {sfOpacity(val, sfMax[si])}">
							{#if val > 0}
								<span class="sf-num">{formatNumber(val)}</span>
								{#if !isHero && heroVal > 0}
									<span class="sf-ratio">{(val / heroVal).toFixed(1)}×</span>
								{/if}
							{/if}
						</td>
					{/each}
					<td class="spark-cell">
						<svg
							viewBox="0 0 {entry.yearlyCites.length - 1} 1"
							class="sparkline"
							preserveAspectRatio="none"
						>
							<path d={sparkAreaPath(entry.yearlyCites, citesMax)} class="cite-area" />
							<path d={sparkLinePath(entry.yearlyCites, citesMax)} class="cite-line" />
							{#if !isHero}
								<path d={sparkLinePath(data.hero.yearlyCites, citesMax)} class="hero-ref-line" />
							{/if}
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
	<div class="sf-tooltip" style="left:{tooltipX}px; top:{tooltipY}px;">
		{data.topSubfields[activeTooltip].name}
	</div>
{/if}

<style>
	.peers-note {
		font-size: var(--text-sm);
		opacity: 0.6;
		margin: 0 0 6px 0;
		display: flex;
		gap: 12px;
		align-items: center;
		flex-wrap: wrap;
	}

	.legend {
		display: flex;
		align-items: center;
		gap: 5px;
		white-space: nowrap;
	}

	.leg-cite {
		display: inline-block;
		width: 22px;
		height: 3px;
		background: rgba(var(--color-range-15), 0.75);
		border-radius: 2px;
		vertical-align: middle;
	}

	.leg-hero-ref {
		display: inline-block;
		width: 22px;
		height: 2px;
		background: transparent;
		border-top: 1px dashed rgba(var(--color-range-15), 0.5);
		vertical-align: middle;
	}

	.peers-table-wrap {
		overflow-x: auto;
	}

	.peers-table {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--text-base);
	}

	thead th {
		font-size: var(--text-xs);
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
		font-size: var(--text-base);
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
		vertical-align: middle;
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
		font-variant-numeric: tabular-nums;
		background: rgba(var(--color-range-15), var(--sf-opacity, 0));
		border-radius: 2px;
	}

	.sf-num {
		display: block;
		font-size: var(--text-sm);
	}

	.sf-ratio {
		display: block;
		font-size: var(--text-xs);
		opacity: 0.55;
	}

	.spark-cell {
		padding: 2px 4px;
		min-width: 80px;
	}

	.sparkline {
		width: 100%;
		height: 56px;
		display: block;
	}

	.cite-area {
		fill: rgba(var(--color-range-15), 0.2);
	}

	.cite-line {
		fill: none;
		stroke: rgba(var(--color-range-15), 0.75);
		stroke-width: 0.06;
		stroke-linejoin: round;
		stroke-linecap: round;
	}

	.hero-ref-line {
		fill: none;
		stroke: rgba(var(--color-range-15), 0.45);
		stroke-width: 0.04;
		stroke-dasharray: 0.22 0.1;
		stroke-linejoin: round;
		stroke-linecap: round;
	}

	.stat-cell {
		text-align: right;
		font-variant-numeric: tabular-nums;
		font-size: var(--text-sm);
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

		.sf-num {
			font-size: 0.9rem;
		}

		.sf-ratio {
			font-size: 0.75rem;
		}

		.stat-cell {
			font-size: 0.9rem;
		}

		.spark-cell {
			min-width: 120px;
		}

		.sparkline {
			height: 72px;
		}
	}
</style>
