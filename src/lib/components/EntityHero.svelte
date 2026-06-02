<script lang="ts">
	import type * as tt from '$lib/tree-types';
	import { REL_TYPES, COMPLETE_YEAR, LATEST_YEAR } from '$lib/constants';
	import { pluralize, formatNumber } from '$lib/text-format-util';
	import { HERO_CONFIG, buildChips, buildLeaderRows } from '$lib/hero-config';
	import YearTicks from '$lib/components/YearTicks.svelte';
	import IndexedCitationLink from '$lib/components/IndexedCitationLink.svelte';

	export let view: tt.View;
	export let rootType: tt.RootType;
	export let semanticId: string;
	export let peersData: tt.EntityPeersResp | null = null;
	export let ladder: tt.LadderData | null = null;
	export let citeText = '';
	export let hitPaperCount = 0;
	export let abstract: string | null = null;
	export let abstractLoading = false;

	const MAX_CHIPS = 5;
	// Suppress the loosest standing band ("top 20%", tier 1): only tier 2+ (top 10% and stricter) is
	// showcase-worthy on the header. The full ladder still surfaces in the Peers section.
	const HERO_MIN_TIER = 2;

	let abstractExpanded = false;
	let ticksHeight: number;

	$: cfg = HERO_CONFIG[rootType];
	$: isHitPaper = rootType === 'hit-papers';
	$: rawCites = parseInt(view.meta?.rawCites ?? '0') || 0;
	$: hIndex = peersData?.hero.hIndex ?? null;
	$: doi = isHitPaper && !semanticId.startsWith('W') ? semanticId : null;

	// Group the flat relation list by type once, keyed by the relation name (paper-topics, …).
	$: grouped = view.primeRelations.reduce(
		(acc, r) => {
			const k = REL_TYPES[r.relType];
			(acc[k] ??= []).push(r);
			return acc;
		},
		{} as Partial<Record<tt.RelTypes, tt.RelatedEntity[]>>
	);

	$: chips = buildChips(cfg, peersData, ladder, grouped, rootType, MAX_CHIPS, HERO_MIN_TIER);
	$: leaderRows = buildLeaderRows(grouped, cfg.leaders);
</script>

<div class="hero">
	<div class="hero-top">
		<h1>{@html view.name}</h1>
		<div class="stat">
			{#if cfg.statVariant === 'paper'}
				<div class="stat-big">{citeText}</div>
				<div class="stat-sub">published {view.startYear}</div>
			{:else if cfg.useRawCites && rawCites > 0}
				<div class="stat-big">{formatNumber(rawCites)} citations</div>
				<div class="stat-sub">
					{pluralize('paper', view.papers)} · {formatNumber(view.citations)}
					<IndexedCitationLink />
					{#if cfg.showHitPapers && hitPaperCount > 0}
						· <a href="#papers">{pluralize('hit paper', hitPaperCount)}</a>
					{/if}
					{#if cfg.showHIndex && hIndex != null}
						· h-index {hIndex}
					{/if}
				</div>
			{:else}
				<div class="stat-big">{formatNumber(view.citations)} citations</div>
				<div class="stat-sub">
					{pluralize('paper', view.papers)} ·
					<IndexedCitationLink />
					{#if cfg.sinceNote === 'complete'}
						· since {COMPLETE_YEAR}
					{:else if cfg.sinceNote === 'startYear'}
						· active since {view.startYear}
					{/if}
				</div>
			{/if}
		</div>
	</div>

	{#if chips.length > 0}
		<ul class="chip-row">
			{#each chips as c (c.name)}
				<li class="chip" style="--chip-c: var({c.colorVar});">
					{#if c.href}
						<a class="chip-name" href={c.href}>{c.name}</a>
					{:else}
						<span class="chip-name">{c.name}</span>
					{/if}
					{#if c.badge}
						<span class="chip-badge" title={c.badgeTitle ?? ''}>{c.badge}</span>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}

	<div class="hero-body">
		<dl class="leaders">
			{#each leaderRows as row (row.label)}
				<div class="leader">
					<dt>{row.label}</dt>
					<dd>
						{#each row.items as it (it.text)}
							{#if it.href}
								<a href={it.href}>{it.text}</a>
							{:else}
								<span>{it.text}</span>
							{/if}
						{/each}
					</dd>
				</div>
			{/each}
		</dl>

		<div class="era">
			<h2>In The Last Decade</h2>
			<div class="era-chart" bind:clientHeight={ticksHeight}>
				<YearTicks
					bottomStacks={view.yearlyPapers}
					topStacks={view.yearlyCites}
					fullHeight={ticksHeight}
					showBottom={!isHitPaper}
					end={LATEST_YEAR}
				/>
			</div>
			{#if isHitPaper}
				<a
					class="dag-link"
					href={doi ? `https://doi.org/${doi}` : `https://openalex.org/${semanticId}`}
					target="_blank"
					rel="noopener">{doi ? `doi.org/${doi}` : 'OpenAlex'} →</a
				>
			{/if}
		</div>
	</div>

	{#if isHitPaper && (abstract || abstractLoading)}
		<details class="abstract" bind:open={abstractExpanded}>
			<summary><h2>Abstract</h2></summary>
			{#if abstract}
				<p class="abstract-text" class:abstract-truncated={!abstractExpanded}>{abstract}</p>
			{:else}
				<p class="abstract-loading">loading…</p>
			{/if}
		</details>
	{/if}
</div>

<style>
	.hero {
		display: flex;
		flex-direction: column;
		gap: 24px;
	}

	.hero-top {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 24px;
		flex-wrap: wrap;
	}

	h1 {
		font-size: clamp(var(--text-2xl), 5.5vw, 3.2rem);
		flex: 1 1 auto;
		min-width: 0;
	}

	.stat {
		text-align: right;
		flex-shrink: 0;
	}

	.stat-big {
		font-weight: 700;
		font-size: var(--text-xl);
		white-space: nowrap;
	}

	.stat-sub {
		font-size: var(--text-sm);
		opacity: 0.8;
		margin-top: 2px;
	}

	.chip-row {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
		gap: 10px;
	}

	.chip {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		padding: 8px 12px;
		text-align: center;
		background-color: rgba(var(--chip-c), 0.16);
		border-bottom: 2px solid rgba(var(--chip-c), 0.55);
	}

	.chip-name {
		font-size: var(--text-sm);
		font-weight: 600;
		color: var(--color-text);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	a.chip-name:hover {
		text-decoration: underline;
	}

	/* Inverse pill: text-bg on color-text guarantees strong contrast in both light and dark themes,
	   independent of the chip's hue (which varies in luminance across the palette). */
	.chip-badge {
		flex-shrink: 0;
		font-size: var(--text-xs);
		font-weight: 700;
		letter-spacing: 0.02em;
		padding: 1px 7px;
		white-space: nowrap;
		color: var(--text-bg);
		background: var(--color-text);
	}

	.hero-body {
		display: flex;
		gap: 48px;
		align-items: flex-start;
		justify-content: center;
		flex-wrap: wrap;
	}

	/* Leaders size to their content (capped); the chart grows to absorb the remaining width so it
	   reaches the edge instead of leaving a gap. On ultra-wide screens the chart caps and the pair
	   centers, so neither block floats. */
	.leaders {
		flex: 0 1 auto;
		max-width: 620px;
		min-width: 280px;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.leader {
		display: grid;
		grid-template-columns: minmax(6rem, 10rem) 1fr;
		column-gap: 14px;
		align-items: baseline;
		min-width: 0;
	}

	.leader dt {
		display: flex;
		align-items: baseline;
		font-weight: 700;
		font-size: var(--text-sm);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		white-space: nowrap;
		opacity: 0.75;
	}

	.leader dt::after {
		content: '';
		flex: 1;
		margin-left: 10px;
		border-bottom: 2px dotted currentColor;
		opacity: 0.5;
		transform: translateY(-3px);
	}

	.leader dd {
		margin: 0;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 2px;
		font-size: var(--text-base);
	}

	.leader dd a:hover {
		text-decoration: underline;
	}

	.era {
		flex: 1 1 320px;
		max-width: 760px;
		min-width: 280px;
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.era h2 {
		text-align: left;
		margin: 0;
	}

	.era-chart {
		width: 100%;
		aspect-ratio: 2.5;
	}

	.dag-link {
		font-size: var(--text-sm);
		opacity: 0.4;
		color: var(--color-text);
		transition: opacity 0.15s;
	}

	.dag-link:hover {
		opacity: 0.8;
	}

	.abstract summary {
		cursor: pointer;
		list-style: none;
	}

	.abstract summary::-webkit-details-marker {
		display: none;
	}

	.abstract summary h2 {
		display: inline;
		font-size: var(--text-sm);
		font-weight: normal;
		opacity: 0.55;
		text-align: left;
	}

	.abstract p {
		font-size: var(--text-base);
		line-height: var(--lh-body);
		opacity: 0.85;
	}

	.abstract-text.abstract-truncated {
		display: -webkit-box;
		-webkit-line-clamp: 4;
		line-clamp: 4;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.abstract-loading {
		opacity: 0.35;
		font-size: var(--text-sm);
	}

	@media (max-width: 700px) {
		.stat {
			text-align: left;
		}
	}
</style>
