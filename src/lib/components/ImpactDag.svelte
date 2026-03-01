<script lang="ts">
	import { afterUpdate, onMount } from 'svelte';
	import type { RefTree, Paper, EntityAttsForLinks } from '$lib/tree-types';
	import { isAuthored } from '$lib/utils/paper-helpers';
	import { computeSeen, buildSubgraphs, classifyComponentLayers } from '$lib/utils/dag-builder';
	import { computeImpactSummary } from '$lib/utils/impact-summary';
	import { pluralize } from '$lib/text-format-util';
	import DagChip from './DagChip.svelte';

	export let dag: RefTree;
	export let paperMap: Record<number, Paper>;
	export let entityAtts: EntityAttsForLinks;
	export let discAuthorNames: Record<string, string>;
	export let authorsMeta: Record<string, { prize: number; year: number }> = {};
	export let sourceAuthorSemId: string | undefined = undefined;
	export let authorName: string = '';

	const MAX_VISIBLE = 2;

	$: pageAuthorDmId = (() => {
		if (!sourceAuthorSemId) return undefined;
		const authors = entityAtts['authors'];
		if (!authors) return undefined;
		for (const [dmId, att] of Object.entries(authors)) {
			if (att.semantic_id === sourceAuthorSemId) return dmId;
		}
		return undefined;
	})();

	$: pageAuthorIsNobel = pageAuthorDmId != null && (authorsMeta[pageAuthorDmId]?.prize ?? 0) > 0;

	$: seen = computeSeen(dag);
	$: components = buildSubgraphs(seen, paperMap);

	$: isAuthoredFn = (wid: number) => {
		const p = paperMap[wid];
		return !!p && !!sourceAuthorSemId && isAuthored(p, sourceAuthorSemId, entityAtts);
	};

	$: componentLayers = components.map(c => classifyComponentLayers(c, seen, isAuthoredFn));

	$: allImpacted = components.flatMap((_, i) => [...componentLayers[i].top, ...componentLayers[i].mid]);
	$: summary = computeImpactSummary(allImpacted, paperMap, entityAtts, authorsMeta);

	let currentIndex = 0;
	$: if (components.length > 0 && currentIndex >= components.length) currentIndex = 0;

	$: currentLayers = componentLayers[currentIndex] ?? { top: [], mid: [], bottom: [] };

	let topExpanded = false;
	let midExpanded = false;
	let bottomExpanded = false;

	function resetExpansion() {
		topExpanded = false;
		midExpanded = false;
		bottomExpanded = false;
		hovered = undefined;
		expanded = new Set();
	}

	function goTo(idx: number) {
		if (idx < 0) idx = components.length - 1;
		if (idx >= components.length) idx = 0;
		currentIndex = idx;
		resetExpansion();
	}

	function onKeydown(e: KeyboardEvent) {
		if (components.length <= 1) return;
		if (e.key === 'ArrowLeft') { goTo(currentIndex - 1); e.preventDefault(); }
		else if (e.key === 'ArrowRight') { goTo(currentIndex + 1); e.preventDefault(); }
	}

	let touchStartX = 0;
	let touchStartY = 0;

	function onTouchStart(e: TouchEvent) {
		touchStartX = e.touches[0].clientX;
		touchStartY = e.touches[0].clientY;
	}

	function onTouchEnd(e: TouchEvent) {
		const dx = e.changedTouches[0].clientX - touchStartX;
		const dy = e.changedTouches[0].clientY - touchStartY;
		if (Math.abs(dx) > 2 * Math.abs(dy) && Math.abs(dx) > 50) {
			goTo(currentIndex + (dx < 0 ? 1 : -1));
		}
	}

	let hovered: number | undefined;
	let expanded = new Set<number>();

	function toggleExpand(wid: number) {
		expanded.has(wid) ? expanded.delete(wid) : expanded.add(wid);
		expanded = expanded;
	}

	$: relatedSet = (() => {
		if (hovered == undefined) return new Set<number>();
		const meta = seen[hovered];
		if (!meta) return new Set<number>();
		const s = new Set<number>();
		const pq = [...meta.parents].filter(p => p !== 0);
		while (pq.length) {
			const p = pq.pop()!;
			if (s.has(p)) continue;
			s.add(p);
			seen[p]?.parents.forEach(pp => { if (pp !== 0 && !s.has(pp)) pq.push(pp); });
		}
		const cq = [...meta.children];
		while (cq.length) {
			const c = cq.pop()!;
			if (s.has(c)) continue;
			s.add(c);
			seen[c]?.children.forEach(cc => { if (!s.has(cc)) cq.push(cc); });
		}
		return s;
	})();

	type ComputedEdge = { path: string; parentWid: number; childWid: number };
	let containerEl: HTMLDivElement;
	let chipEls: Record<number, HTMLDivElement> = {};
	let edges: ComputedEdge[] = [];

	$: currentWids = new Set([...currentLayers.top, ...(midExpanded ? currentLayers.mid : []), ...currentLayers.bottom]);

	function computeEdges() {
		if (!containerEl) { edges = []; return; }
		const containerRect = containerEl.getBoundingClientRect();
		const newEdges: ComputedEdge[] = [];
		for (const [widStr, meta] of Object.entries(seen)) {
			const parentWid = Number(widStr);
			if (!currentWids.has(parentWid)) continue;
			const parentEl = chipEls[parentWid];
			if (!parentEl) continue;
			for (const childWid of meta.children) {
				if (!currentWids.has(childWid)) continue;
				const childEl = chipEls[childWid];
				if (!childEl) continue;
				const pRect = parentEl.getBoundingClientRect();
				const cRect = childEl.getBoundingClientRect();
				const startX = pRect.left + pRect.width / 2 - containerRect.left;
				const startY = pRect.bottom - containerRect.top;
				const endX = cRect.left + cRect.width / 2 - containerRect.left;
				const endY = cRect.top - containerRect.top;
				const rawGap = endY - startY;
				let path: string;
				if (rawGap <= 10) {
					const arcDepth = 18;
					const midX = (startX + endX) / 2;
					const belowY = Math.max(startY, endY) + arcDepth;
					path = `M ${startX} ${startY} Q ${midX} ${belowY}, ${endX} ${endY}`;
				} else {
					const cp1y = startY + rawGap * 0.4;
					const cp2y = endY - rawGap * 0.4;
					path = `M ${startX} ${startY} C ${startX} ${cp1y}, ${endX} ${cp2y}, ${endX} ${endY}`;
				}
				newEdges.push({ path, parentWid, childWid });
			}
		}
		edges = newEdges;
	}

	function edgeOpacity(edge: ComputedEdge): number {
		if (hovered == undefined) return 0.06;
		if (
			(edge.parentWid === hovered || relatedSet.has(edge.parentWid)) &&
			(edge.childWid === hovered || relatedSet.has(edge.childWid))
		) return 0.5;
		return 0.02;
	}

	let resizeObserver: ResizeObserver | undefined;
	onMount(() => {
		resizeObserver = new ResizeObserver(() => computeEdges());
		if (containerEl) resizeObserver.observe(containerEl);
		return () => resizeObserver?.disconnect();
	});
	afterUpdate(() => computeEdges());

	function sortByYear(wids: number[]): number[] {
		return [...wids].sort((a, b) => (paperMap[b]?.year ?? 0) - (paperMap[a]?.year ?? 0));
	}

	$: visibleTop = sortByYear(topExpanded ? currentLayers.top : currentLayers.top.slice(0, MAX_VISIBLE));
	$: hiddenTopCount = Math.max(0, currentLayers.top.length - MAX_VISIBLE);
	$: visibleBottom = sortByYear(bottomExpanded ? currentLayers.bottom : currentLayers.bottom.slice(0, MAX_VISIBLE));
	$: hiddenBottomCount = Math.max(0, currentLayers.bottom.length - MAX_VISIBLE);
	$: visibleMid = midExpanded ? sortByYear(currentLayers.mid) : [];

	$: refLabel = authorName ? `Works of ${authorName} being referenced` : 'Referenced Works';
</script>

<svelte:window on:keydown={onKeydown} />

<!-- svelte-ignore a11y-no-static-element-interactions -->
<div class="impact-dag" bind:this={containerEl} on:touchstart={onTouchStart} on:touchend={onTouchEnd}>
	{#if summary.nobelCount > 0 || summary.prestigiousCount > 0 || summary.standoutCount > 0}
		<div class="summary-labels">
			{#if summary.nobelCount > 0}
				<span class="summary-badge hl-nobel">{summary.nobelCount} by Nobel laureates</span>
			{/if}
			{#if summary.prestigiousCount > 0}
				<span class="summary-badge hl-prestigious">{summary.prestigiousCount} from Science/Nature</span>
			{/if}
			{#if summary.standoutCount > 0}
				<span class="summary-badge hl-hit">{summary.standoutCount} standout</span>
			{/if}
		</div>
	{/if}

	{#if components.length > 1}
		<div class="subgraph-nav">
			<button class="nav-btn" on:click={() => goTo(currentIndex - 1)} aria-label="Previous sub-graph">&larr;</button>
			<span class="nav-label">Sub-graph {currentIndex + 1} of {components.length}</span>
			<button class="nav-btn" on:click={() => goTo(currentIndex + 1)} aria-label="Next sub-graph">&rarr;</button>
		</div>
	{/if}

	<svg class="edge-overlay" aria-hidden="true">
		{#each edges as edge}
			<path d={edge.path} stroke="currentColor" stroke-width="1.2" fill="none" opacity={edgeOpacity(edge)} />
		{/each}
	</svg>

	{#if currentLayers.top.length > 0}
		<div class="level-section">
			<h4 class="level-label">Citing Papers</h4>
			<div class="chips">
				{#each visibleTop as wid (wid)}
					<div class="chip-wrap" bind:this={chipEls[wid]}>
						<DagChip
							paper={paperMap[wid]}
							{wid}
							{entityAtts}
							{discAuthorNames}
							{authorsMeta}
							{pageAuthorDmId}
							{pageAuthorIsNobel}
							isHovered={hovered === wid}
							isRelated={relatedSet.has(wid)}
							dimmed={hovered != undefined && hovered !== wid && !relatedSet.has(wid)}
							isExpanded={expanded.has(wid)}
							on:toggle={e => toggleExpand(e.detail)}
							on:hover={e => { hovered = e.detail; }}
							on:leave={() => { hovered = undefined; }}
						/>
					</div>
				{/each}
			</div>
			{#if !topExpanded && hiddenTopCount > 0}
				<!-- svelte-ignore a11y-click-events-have-key-events -->
				<!-- svelte-ignore a11y-no-static-element-interactions -->
				<span class="expand-link" on:click={() => { topExpanded = true; }}>and {hiddenTopCount} more</span>
			{:else if topExpanded && hiddenTopCount > 0}
				<!-- svelte-ignore a11y-click-events-have-key-events -->
				<!-- svelte-ignore a11y-no-static-element-interactions -->
				<span class="expand-link" on:click={() => { topExpanded = false; }}>see less</span>
			{/if}
		</div>
	{/if}

	{#if currentLayers.mid.length > 0}
		<div class="level-section">
			{#if midExpanded}
				<h4 class="level-label">Intermediate Papers
					<!-- svelte-ignore a11y-click-events-have-key-events -->
					<!-- svelte-ignore a11y-no-static-element-interactions -->
					<span class="expand-link" on:click={() => { midExpanded = false; }}>see less</span>
				</h4>
				<div class="chips">
					{#each visibleMid as wid (wid)}
						<div class="chip-wrap" bind:this={chipEls[wid]}>
							<DagChip
								paper={paperMap[wid]}
								{wid}
								{entityAtts}
								{discAuthorNames}
								{authorsMeta}
								{pageAuthorDmId}
								{pageAuthorIsNobel}
								isHovered={hovered === wid}
								isRelated={relatedSet.has(wid)}
								dimmed={hovered != undefined && hovered !== wid && !relatedSet.has(wid)}
								isExpanded={expanded.has(wid)}
								on:toggle={e => toggleExpand(e.detail)}
								on:hover={e => { hovered = e.detail; }}
								on:leave={() => { hovered = undefined; }}
							/>
						</div>
					{/each}
				</div>
			{:else}
				<!-- svelte-ignore a11y-click-events-have-key-events -->
				<!-- svelte-ignore a11y-no-static-element-interactions -->
				<span class="expand-link mid-summary" on:click={() => { midExpanded = true; }}>
					{pluralize('intermediate paper', currentLayers.mid.length)}
				</span>
			{/if}
		</div>
	{/if}

	{#if currentLayers.bottom.length > 0}
		<div class="level-section">
			<h4 class="level-label">{refLabel}</h4>
			<div class="chips">
				{#each visibleBottom as wid (wid)}
					<div class="chip-wrap" bind:this={chipEls[wid]}>
						<DagChip
							paper={paperMap[wid]}
							{wid}
							{entityAtts}
							{discAuthorNames}
							{authorsMeta}
							{pageAuthorDmId}
							{pageAuthorIsNobel}
							isHovered={hovered === wid}
							isRelated={relatedSet.has(wid)}
							dimmed={hovered != undefined && hovered !== wid && !relatedSet.has(wid)}
							isExpanded={expanded.has(wid)}
							on:toggle={e => toggleExpand(e.detail)}
							on:hover={e => { hovered = e.detail; }}
							on:leave={() => { hovered = undefined; }}
						/>
					</div>
				{/each}
			</div>
			{#if !bottomExpanded && hiddenBottomCount > 0}
				<!-- svelte-ignore a11y-click-events-have-key-events -->
				<!-- svelte-ignore a11y-no-static-element-interactions -->
				<span class="expand-link" on:click={() => { bottomExpanded = true; }}>and {hiddenBottomCount} more</span>
			{:else if bottomExpanded && hiddenBottomCount > 0}
				<!-- svelte-ignore a11y-click-events-have-key-events -->
				<!-- svelte-ignore a11y-no-static-element-interactions -->
				<span class="expand-link" on:click={() => { bottomExpanded = false; }}>see less</span>
			{/if}
		</div>
	{/if}
</div>

<style>
	.impact-dag {
		display: flex;
		flex-direction: column;
		position: relative;
		gap: 12px;
	}

	.summary-labels {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		margin-bottom: 4px;
	}

	.summary-badge {
		display: inline-block;
		padding: 2px 8px;
		border-radius: 4px;
		font-size: 0.7rem;
		font-weight: 600;
	}

	.subgraph-nav {
		display: flex;
		align-items: center;
		gap: 8px;
		justify-content: center;
	}

	.nav-btn {
		background: none;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		border-radius: 4px;
		padding: 2px 10px;
		cursor: pointer;
		font-size: 0.85rem;
		color: var(--color-text);
	}

	.nav-btn:hover {
		background: rgba(var(--color-range-15), 0.08);
	}

	.nav-label {
		font-size: 0.8rem;
		opacity: 0.6;
	}

	.edge-overlay {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		pointer-events: none;
		overflow: visible;
		color: var(--color-text);
	}

	.level-section {
		display: flex;
		flex-direction: column;
		gap: 6px;
		position: relative;
	}

	.level-label {
		margin: 0;
		font-size: 0.85rem;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		opacity: 0.5;
	}

	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		padding-bottom: 2px;
	}

	.chip-wrap {
		flex: 1 0 160px;
		max-width: 380px;
	}

	.expand-link {
		font-size: 0.75rem;
		opacity: 0.5;
		cursor: pointer;
		text-decoration: underline;
		text-underline-offset: 2px;
	}

	.expand-link:hover {
		opacity: 0.8;
	}

	.mid-summary {
		text-align: center;
		padding: 6px 0;
		font-style: italic;
	}

	.hl-hit {
		background: var(--badge-hit-bg);
		color: var(--badge-hit-text);
	}

	.hl-prestigious {
		background: var(--badge-prestigious-bg);
		color: var(--badge-prestigious-text);
	}

	.hl-nobel {
		background: var(--badge-award-bg);
		color: var(--badge-award-text);
	}

	@media (min-width: 1200px) {
		.level-label {
			font-size: 1.15rem;
		}

		.summary-badge {
			font-size: 0.85rem;
		}

		.chip-wrap {
			flex-basis: 300px;
		}
	}
</style>
