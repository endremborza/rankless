<script lang="ts">
	import { onMount, tick } from 'svelte';
	import type { ImpactHighlightsResp } from '$lib/wire/rankless_server/highlights';
	import { formatNumber } from '$lib/text-format-util';
	import { byCiterOrder, citedLayer, highlightsView, ownCard } from '$lib/utils/impact-highlights';
	import { citeCurve } from '$lib/utils/impact-card';
	import HighlightCard from './HighlightCard.svelte';

	export let resp: ImpactHighlightsResp;
	export let authorName: string;

	type Hover = { top: boolean; i: number };
	type Edge = { d: string; t: number; b: number };

	const MAX_PER_PAGE = 4;
	const MIN_SLOT = 160;

	let page = 0;
	let width = 0;
	let hovered: Hover | undefined;
	let box: HTMLDivElement;
	let topEls: HTMLElement[] = [];
	let bottomEls: HTMLElement[] = [];
	let edges: Edge[] = [];

	$: rows = highlightsView(resp);
	$: perPage =
		width > 0 ? Math.max(1, Math.min(MAX_PER_PAGE, Math.floor(width / MIN_SLOT))) : MAX_PER_PAGE;
	$: pages = Math.ceil(rows.length / perPage);
	$: if (page >= pages) page = Math.max(0, pages - 1);
	$: top = rows.slice(page * perPage, (page + 1) * perPage);
	$: layer = byCiterOrder(citedLayer(top, top.length));
	$: own = layer.papers.map((p) => ownCard(p, resp));
	$: litTop = related(hovered, layer.links, true);
	$: litBottom = related(hovered, layer.links, false);
	$: litEdges = edges.map(
		(e) => !!hovered && (hovered.top ? e.t === hovered.i : e.b === hovered.i)
	);
	$: if (layer) measure();

	onMount(() => {
		const observer = new ResizeObserver(() => measure());
		observer.observe(box);
		return () => observer.disconnect();
	});

	// The chips of one row lit by the hovered chip: itself, or those it is linked to.
	function related(h: Hover | undefined, links: [number, number][], topRow: boolean): Set<number> {
		if (!h) return new Set();
		if (h.top === topRow) return new Set([h.i]);
		return new Set(links.filter((l) => l[h.top ? 0 : 1] === h.i).map((l) => l[topRow ? 0 : 1]));
	}

	async function measure() {
		await tick();
		if (!box) return;
		const o = box.getBoundingClientRect();
		edges = layer.links.flatMap(([t, b]) => {
			const from = topEls[t]?.getBoundingClientRect();
			const to = bottomEls[b]?.getBoundingClientRect();
			if (!from || !to) return [];
			const d = citeCurve(
				from.left + from.width / 2 - o.left,
				from.bottom - o.top,
				to.left + to.width / 2 - o.left,
				to.top - o.top
			);
			return [{ d, t, b }];
		});
	}

	function turn(by: number) {
		page = (page + by + pages) % pages;
		hovered = undefined;
	}
</script>

<div class="graph" bind:this={box} bind:clientWidth={width}>
	<svg class="edges" aria-hidden="true">
		{#each edges as e, i (i)}
			<path d={e.d} class:lit={litEdges[i]} class:dim={!!hovered && !litEdges[i]} />
		{/each}
	</svg>

	<div class="row-label">
		Citing papers
		{#if pages > 1}
			<span class="pager">
				<button on:click={() => turn(-1)} aria-label="Previous citing papers">‹</button>
				{perPage > 1 ? `${page * perPage + 1}–${page * perPage + top.length}` : page + 1} of {rows.length}
				<button on:click={() => turn(1)} aria-label="Next citing papers">›</button>
			</span>
		{/if}
	</div>
	<div class="row">
		{#each top as row, i (i)}
			<div
				class="chip"
				class:lit={litTop.has(i)}
				class:dim={!!hovered && !litTop.has(i)}
				bind:this={topEls[i]}
				role="group"
				on:mouseenter={() => (hovered = { top: true, i })}
				on:mouseleave={() => (hovered = undefined)}
				on:focusin={() => (hovered = { top: true, i })}
				on:focusout={() => (hovered = undefined)}
			>
				<HighlightCard card={row} />
			</div>
		{/each}
	</div>

	<div class="own-band">
		<div class="row">
			{#each own as card, i (i)}
				<div
					class="chip own"
					class:lit={litBottom.has(i)}
					class:dim={!!hovered && !litBottom.has(i)}
					bind:this={bottomEls[i]}
					role="group"
					on:mouseenter={() => (hovered = { top: false, i })}
					on:mouseleave={() => (hovered = undefined)}
					on:focusin={() => (hovered = { top: false, i })}
					on:focusout={() => (hovered = undefined)}
				>
					<HighlightCard {card} />
				</div>
			{/each}
		</div>
		<div class="row-label own-label">{authorName}'s papers they cite</div>
	</div>
</div>

<p class="note">
	Independent citations only: {formatNumber(resp.totals.independent)} of {formatNumber(
		resp.totals.citingPapers
	)} citing papers, leaving out {authorName}'s own, their co-authors' and those from institutions
	{authorName} has worked at.
</p>

<style>
	.graph {
		position: relative;
		display: flex;
		flex-direction: column;
		margin: 12px 0 14px;
	}

	.edges {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		pointer-events: none;
		overflow: visible;
	}

	.edges path {
		fill: none;
		stroke: var(--color-theme-blue);
		stroke-width: 1.4;
		opacity: 0.45;
		transition: opacity 160ms;
	}

	.edges path.lit {
		opacity: 0.95;
		stroke-width: 2;
	}

	.edges path.dim {
		opacity: 0.08;
	}

	.row-label {
		font-size: var(--text-xs);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		opacity: 0.6;
		text-align: center;
	}

	.pager {
		margin-left: 8px;
		text-transform: none;
		letter-spacing: normal;
	}

	.pager button {
		background: none;
		border: 1px solid rgba(var(--color-range-15), 0.3);
		border-radius: 4px;
		padding: 0 7px;
		color: var(--color-theme-blue);
		font: inherit;
		cursor: pointer;
	}

	.row {
		display: flex;
		justify-content: center;
		gap: 10px;
		margin: 6px 0;
	}

	.own-band {
		margin-top: 48px;
		padding: 10px 10px 8px;
		border-radius: 8px;
		background: rgba(var(--color-range-15), 0.08);
	}

	.own-label {
		color: var(--color-theme-blue);
		opacity: 1;
		font-weight: 600;
	}

	.chip {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: 4px;
		flex: 1 1 0;
		min-width: 0;
		max-width: 290px;
		padding: 8px 10px;
		white-space: normal;
		border: 1px solid rgba(127, 127, 127, 0.3);
		border-radius: 6px;
		background: var(--text-bg);
		transition:
			border-color 160ms,
			opacity 160ms;
	}

	.chip.own {
		border: 1px solid rgba(var(--color-range-15), 0.45);
		border-left: 4px solid var(--color-theme-blue);
		background:
			linear-gradient(rgba(var(--color-range-15), 0.16), rgba(var(--color-range-15), 0.16)),
			var(--text-bg);
	}

	.chip.lit {
		border-color: var(--color-theme-blue);
		box-shadow: 0 0 0 1px var(--color-theme-blue);
	}

	.chip.dim {
		opacity: 0.45;
	}

	.note {
		margin: 10px 0 0;
		font-size: var(--text-xs);
		opacity: 0.65;
		text-align: center;
	}
</style>
