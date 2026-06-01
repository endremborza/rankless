<script lang="ts">
	import type * as tt from '$lib/tree-types';
	import { REL_TYPES, ROOT_TYPES, LATEST_YEAR } from '$lib/constants';
	import { entToLink } from '$lib/tree-functions';
	import { pluralize, formatNumber } from '$lib/text-format-util';
	import {
		sfColorVar,
		tierLabels,
		citStandingTier,
		standingLabel,
		standingPhrase
	} from '$lib/peers-utils';
	import YearTicks from '$lib/components/YearTicks.svelte';
	import HoverBlock from '$lib/components/HoverBlock.svelte';

	export let view: tt.View;
	export let rootType: tt.RootType;
	export let semanticId: string;
	export let peersData: tt.EntityPeersResp | null = null;
	export let ladder: tt.LadderData | null = null;
	export let citeText = '';
	export let hitPaperCount = 0;
	export let abstract: string | null = null;

	const MAX_CHIPS = 5;
	const MAX_LEADER_ITEMS = 3;
	// Suppress the loosest standing band ("top 20%", tier 1): only tier 2+ (top 10% and stricter) is
	// showcase-worthy on the header. The full ladder still surfaces in the Peers section.
	const HERO_MIN_TIER = 2;

	type Chip = {
		name: string;
		href: string | null;
		colorVar: string;
		badge: string | null;
		badgeTitle: string | null;
	};
	type LeaderItem = { text: string; href: string | null };
	type LeaderRow = { label: string; items: LeaderItem[] };

	let showIndexedCiteText = false;
	let abstractExpanded = false;
	let ticksHeight: number;

	$: isHitPaper = rootType === 'hit-papers';
	$: rawCites = parseInt(view.meta?.rawCites ?? '0') || 0;
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

	function rootHref(etype: tt.EntityType, sid: string): string | null {
		return ROOT_TYPES.includes(etype as tt.RootType) && sid
			? entToLink({ rootType: etype as tt.RootType, semanticId: sid })
			: null;
	}

	$: labels = ladder ? tierLabels(ladder.pctBands) : [];

	// Field chips: when peer data is present they carry the hero's per-subfield standing badge and
	// align (color + order) with the Peers section. Otherwise fall back to the raw paper-fields
	// relations — same subfields, no standing (no ladder for this root type).
	$: chips = peersData
		? peersData.topSubfields.slice(0, MAX_CHIPS).map((sf, i): Chip => {
				const tier = ladder
					? citStandingTier(ladder.ladder[sf.dmId] ?? [], peersData!.hero.subfieldCitations[i] ?? 0)
					: 0;
				const show = tier >= HERO_MIN_TIER;
				return {
					name: sf.name,
					href: entToLink({ rootType: 'subfields', semanticId: sf.semanticId }),
					colorVar: sfColorVar(i),
					badge: show ? standingLabel(tier, labels) : null,
					badgeTitle: show ? standingPhrase(tier, labels, rootType, sf.name) : null
				};
			})
		: (grouped['paper-fields'] ?? []).slice(0, MAX_CHIPS).map(
				(r, i): Chip => ({
					name: r.name,
					href: rootHref(r.etype, r.semanticId),
					colorVar: sfColorVar(i),
					badge: null,
					badgeTitle: null
				})
			);

	function relRow(
		label: string,
		key: tt.RelTypes,
		withCount: boolean,
		n: number
	): LeaderRow | null {
		const rels = (grouped[key] ?? []).slice(0, n);
		if (rels.length === 0) return null;
		return {
			label,
			items: rels.map((r) => ({
				text: withCount ? `${r.name} (${pluralize('paper', r.score)})` : r.name,
				href: rootHref(r.etype, r.semanticId)
			}))
		};
	}

	// A paper lists its people/venue; every other entity lists what it works on and where.
	// TODO(topic-tags): once topic creator/dominator tags land, surface a "Originated / Dominates"
	// leader row here from the new hit-paper / entity payload fields.
	$: leaderRows = (
		isHitPaper
			? [
					relRow('Authors', 'paper-authors', false, 5),
					relRow('Journal', 'paper-journals', false, 1)
				]
			: [
					relRow('Topics', 'paper-topics', true, MAX_LEADER_ITEMS),
					relRow('Journals', 'paper-journals', false, MAX_LEADER_ITEMS),
					relRow('Geography', 'collab-nation', false, MAX_LEADER_ITEMS)
				]
	).filter((r): r is LeaderRow => r !== null);
</script>

<div class="hero">
	<div class="hero-top">
		<h1>{@html view.name}</h1>
		<div class="stat">
			<HoverBlock
				show={showIndexedCiteText}
				style="top: 20svh; left:20vw; width: 60vw;max-width: 550px"
			>
				Citations made by non-retracted papers categorized as "article", "book", or "review" that
				have received at least one citation.
			</HoverBlock>
			{#if isHitPaper}
				<div class="stat-big">{citeText}</div>
				<div class="stat-sub">published {view.startYear}</div>
			{:else if rawCites > 0}
				<div class="stat-big">{formatNumber(rawCites)} citations</div>
				<div class="stat-sub">
					{pluralize('paper', view.papers)} · {formatNumber(view.citations)}
					<a
						href="/#indexed-citation"
						target="blank_"
						on:mouseover={() => (showIndexedCiteText = true)}
						on:mouseleave={() => (showIndexedCiteText = false)}
						on:focus={() => (showIndexedCiteText = true)}
						on:blur={() => (showIndexedCiteText = false)}>indexed</a
					>
					{#if hitPaperCount > 0}
						· <a href="#papers">{pluralize('hit paper', hitPaperCount)}</a>
					{/if}
				</div>
			{:else}
				<div class="stat-big">{formatNumber(view.citations)} citations</div>
				<div class="stat-sub">
					{pluralize('paper', view.papers)} ·
					<a
						href="/#indexed-citation"
						target="blank_"
						on:mouseover={() => (showIndexedCiteText = true)}
						on:mouseleave={() => (showIndexedCiteText = false)}
						on:focus={() => (showIndexedCiteText = true)}
						on:blur={() => (showIndexedCiteText = false)}>indexed</a
					>
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

	{#if isHitPaper}
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
