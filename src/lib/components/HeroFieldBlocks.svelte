<script lang="ts">
	import { fly } from 'svelte/transition';
	import { quintOut } from 'svelte/easing';
	import type { HeroTile } from '$lib/hero-config';
	import { pluralize, formatNumber } from '$lib/text-format-util';

	// Impact side = specialization subfields with "top X%" badges + citing-topics (X-citations hover).
	// Production side = paper-fields + paper-topics with papers-authored counts. Two color families.
	export let impactTiles: HeroTile[] = [];
	export let productionTiles: HeroTile[] = [];
	export let impactLabel = 'Impact in';
	export let productionLabel = 'Papers in';
	// Tiles shown per block before the user expands — two each fills the one row a block allows.
	export let defaultVisible = 2;

	// Cascade the revealed tiles in one after another instead of snapping the whole set into place.
	const STAGGER = 45;

	let expanded = false;

	$: canExpand = impactTiles.length > defaultVisible || productionTiles.length > defaultVisible;
	$: impactVisible = expanded ? impactTiles : impactTiles.slice(0, defaultVisible);
	$: productionVisible = expanded ? productionTiles : productionTiles.slice(0, defaultVisible);
	$: blocks = [
		{ key: 'impact', label: impactLabel, tiles: impactVisible },
		{ key: 'production', label: productionLabel, tiles: productionVisible }
	];
</script>

{#if impactTiles.length > 0 || productionTiles.length > 0}
	<div class="field-blocks">
		{#each blocks as b (b.key)}
			{#if b.tiles.length > 0}
				<section class="block">
					<h3 class="block-label">
						{b.label}
						{#if b.key === 'production' && b.tiles.some((t) => t.count != null)}
							<span
								class="block-note"
								title="A paper can belong to several fields and topics, so these counts can add up to more than the total number of papers."
								aria-label="A paper can belong to several fields and topics, so these counts can add up to more than the total number of papers."
								>ⓘ</span
							>
						{/if}
					</h3>
					<ul class="tiles">
						{#each b.tiles as t, i (i)}
							<li
								class="tile"
								style="--tile-c: {t.tileColor};"
								in:fly|local={{
									y: 10,
									duration: 260,
									delay: Math.max(0, i - defaultVisible) * STAGGER,
									easing: quintOut
								}}
								out:fly|local={{ y: 8, duration: 140, easing: quintOut }}
							>
								<div class="tile-head">
									{#if t.href}
										<a class="tile-name" href={t.href}>{t.name}</a>
									{:else}
										<span class="tile-name">{t.name}</span>
									{/if}
									{#if t.badge}
										<span class="tile-badge" title={t.badgeTitle ?? ''}>{t.badge}</span>
									{:else if t.count != null}
										<span class="tile-count" title={`${pluralize('paper', t.count)} authored`}>
											{formatNumber(t.count)}
										</span>
									{/if}
								</div>
								{#if t.topics.length > 0}
									<ul class="tile-topics">
										{#each t.topics as tp, j (j)}
											<li title={tp.hover}>
												<span class="topic-name">{tp.name}</span>
												{#if tp.count != null}
													<span class="topic-count">{formatNumber(tp.count)}</span>
												{/if}
											</li>
										{/each}
									</ul>
								{/if}
							</li>
						{/each}
					</ul>
				</section>
			{/if}
		{/each}
	</div>
	{#if canExpand}
		<button type="button" class="expand-btn" on:click={() => (expanded = !expanded)}>
			{expanded ? 'show fewer fields' : 'show more fields'}
		</button>
	{/if}
{/if}

<style>
	/* Two blocks side by side on a wide screen (stacking on narrow); two tiles each by default puts
	   four across in one row. The expand toggle reveals every top subfield on both sides at once. */
	.field-blocks {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 12px 24px;
		align-items: start;
	}

	.block {
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	.block-label {
		margin: 0;
		font-size: var(--text-xs);
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		opacity: 0.55;
	}

	.block-note {
		margin-left: 4px;
		font-weight: 400;
		cursor: help;
	}

	/* Two tiles per row within a block; the expand toggle stacks the rest in fresh rows beneath. */
	.tiles {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 10px;
		align-content: start;
	}

	.tile {
		display: flex;
		flex-direction: column;
		gap: 6px;
		padding: 8px 12px;
		background-color: rgba(var(--tile-c), 0.16);
		border-bottom: 2px solid rgba(var(--tile-c), 0.55);
	}

	/* flex-start keeps the badge/count pinned to the top-right even when a long subfield name wraps
	   to a second line, so the label never splits the name mid-flow. */
	.tile-head {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 8px;
	}

	.tile-name {
		font-size: var(--text-sm);
		font-weight: 600;
		color: var(--color-text);
		min-width: 0;
		overflow-wrap: anywhere;
	}

	a.tile-name:hover {
		text-decoration: underline;
	}

	/* Inverse pill: text-bg on color-text reads clearly over any tile hue, light or dark. */
	.tile-badge {
		flex-shrink: 0;
		font-size: var(--text-xs);
		font-weight: 700;
		letter-spacing: 0.02em;
		padding: 1px 7px;
		white-space: nowrap;
		color: var(--text-bg);
		background: var(--color-text);
	}

	.tile-count {
		flex-shrink: 0;
		font-size: var(--text-sm);
		font-weight: 700;
		opacity: 0.7;
		font-variant-numeric: tabular-nums;
	}

	.tile-topics {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 1px;
	}

	.tile-topics li {
		display: flex;
		justify-content: space-between;
		gap: 8px;
		font-size: var(--text-xs);
		opacity: 0.85;
		cursor: default;
	}

	.topic-name {
		min-width: 0;
		overflow-wrap: anywhere;
	}

	.topic-count {
		flex-shrink: 0;
		opacity: 0.55;
		font-variant-numeric: tabular-nums;
	}

	.expand-btn {
		align-self: center;
		margin-top: 10px;
		padding: 3px 14px;
		font-size: var(--text-xs);
		font-weight: 600;
		letter-spacing: 0.03em;
		text-transform: uppercase;
		color: var(--color-text);
		background: transparent;
		border: 1px solid currentColor;
		border-radius: 999px;
		cursor: pointer;
		opacity: 0.5;
		transition: opacity 0.15s;
	}

	.expand-btn:hover {
		opacity: 0.85;
	}

	@media (max-width: 640px) {
		.field-blocks {
			grid-template-columns: 1fr;
		}

		.tiles {
			grid-template-columns: 1fr;
		}
	}
</style>
