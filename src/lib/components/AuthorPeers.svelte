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

	function sparkBars(entry: PeerAuthorEntry): { papers: number[]; cites: number[] } {
		return { papers: entry.yearlyPapers, cites: entry.yearlyCites };
	}

	function sparkMax(entries: PeerAuthorEntry[]): { papers: number; cites: number } {
		return {
			papers: Math.max(1, ...entries.flatMap((e) => e.yearlyPapers)),
			cites: Math.max(1, ...entries.flatMap((e) => e.yearlyCites))
		};
	}

	$: sMax = sparkMax(allEntries);

	function abbrSfName(name: string): string {
		const words = name.split(/\s+/);
		if (words.length <= 2 || name.length <= 18) return name;
		return words.map((w) => (/^(and|of|the|in|for)$/i.test(w) ? '' : w[0])).filter(Boolean).join('');
	}
</script>

<div class="peers-table-wrap">
	<table class="peers-table">
		<thead>
			<tr>
				<th class="name-col">Author</th>
				{#each data.topSubfields as sf, si}
					<th class="sf-col" title={sf.name}>
						<a href="/subfields/{sf.semanticId}">{abbrSfName(sf.name)}</a>
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
				{@const bars = sparkBars(entry)}
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
						<svg viewBox="0 0 {bars.papers.length} 2" class="sparkline" preserveAspectRatio="none">
							{#each bars.cites as c, i}
								<rect
									x={i}
									y={0}
									width={0.8}
									height={c / sMax.cites}
									class="cite-bar"
								/>
							{/each}
							{#each bars.papers as p, i}
								<rect
									x={i}
									y={1}
									width={0.8}
									height={p / sMax.papers}
									class="paper-bar"
								/>
							{/each}
							<line x1={0} x2={bars.papers.length} y1={1} y2={1} class="axis" />
						</svg>
					</td>
					<td class="stat-cell">{formatNumber(entry.papers)}</td>
					<td class="stat-cell">{formatNumber(entry.citations)}</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>

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

	thead th a {
		color: inherit;
		text-decoration: none;
	}

	thead th a:hover {
		text-decoration: underline;
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

		.sf-cell, .stat-cell {
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
