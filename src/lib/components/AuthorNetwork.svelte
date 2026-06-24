<script lang="ts">
	import { circleLayout, getIndex } from '$lib/network-util';
	import type { cytoscapeLayout } from '$lib/network-force';
	import type { EntityAttsForLinks, Paper, RelatedEntity } from '$lib/tree-types';
	import type { WorksLoader } from '$lib/utils/works-loader';
	import { fetchWorkIntersection } from '$lib/utils/works-intersection';
	import { isAuthored, resolveSourceName } from '$lib/utils/paper-helpers';
	import { onMount } from 'svelte';
	import { fade, slide } from 'svelte/transition';
	import AuthorTimeline from './AuthorTimeline.svelte';

	export let authors: RelatedEntity[] = [];
	export let edgeWeights: number[] = [];
	export let rootName: string = 'Person';
	export let heroSemanticId: string = '';
	export let works: WorksLoader;

	type Selection = { kind: 'node'; i: number } | { kind: 'edge'; i: number; j: number } | null;

	$: n = authors.length;
	$: nodeIds = authors.map((a) => a.semanticId);
	$: nodeScales = scaledNodeScalars(authors.map((a) => a.score));

	let selection: Selection = null;
	let hovered: Selection = null;
	$: focus = hovered ?? selection;

	let view: 'network' | 'timeline' = 'network';

	// Reset the drilldown when the hero changes (component is reused across navigations).
	let seenHero = '';
	$: if (heroSemanticId !== seenHero) {
		seenHero = heroSemanticId;
		selection = null;
		hovered = null;
		view = 'network';
	}

	// The timeline places every collaborator, so it needs the full work set, not just the page.
	let timelineLoadedFor = '';
	$: if (view === 'timeline' && timelineLoadedFor !== heroSemanticId) {
		timelineLoadedFor = heroSemanticId;
		works.loadAll();
	}

	// The first drilldown needs every work to find all shared papers; pull them lazily and once.
	// The loader is shared with the works table, so this is free if that has already loaded.
	let loadedFor = '';
	$: if (selection && loadedFor !== heroSemanticId) {
		loadedFor = heroSemanticId;
		works.loadAll();
	}

	$: selectionIds =
		selection === null
			? []
			: selection.kind === 'node'
				? [nodeIds[selection.i]]
				: [nodeIds[selection.i], nodeIds[selection.j]];

	$: selectedPapers =
		selection === null
			? []
			: $works.papers
					.filter((p) =>
						selectionIds.every((id) => id !== '' && isAuthored(p, id, $works.entityAtts))
					)
					.sort((a, b) => b.citations - a.citations);

	$: selectionTitle =
		selection === null
			? ''
			: selection.kind === 'node'
				? `${rootName} & ${authors[selection.i].name}`
				: `${rootName}, ${authors[selection.i].name} & ${authors[selection.j].name}`;

	$: worksLoading = !$works.allLoaded;

	// Two-way "their own shared papers" fallback for edges: aworks(i) ∩ aworks(j), hero excluded.
	// An edge weight reflects the pair's GLOBAL co-authorship, so it can be present even when the
	// hero shares no paper with both — then the three-way `selectedPapers` is empty and we offer to
	// load the pair's intersection from the backend instead.
	let pairPapers: Paper[] | null = null;
	let pairEntityAtts: EntityAttsForLinks = {};
	let pairTotal = 0;
	let pairLoading = false;
	let pairError = false;

	$: edgeKey = selection?.kind === 'edge' ? `${selection.i}-${selection.j}` : '';
	let loadedPairKey = '';
	$: if (edgeKey !== loadedPairKey) {
		loadedPairKey = edgeKey;
		pairPapers = null;
		pairEntityAtts = {};
		pairTotal = 0;
		pairLoading = false;
		pairError = false;
	}

	$: showingPair = selection?.kind === 'edge' && pairPapers !== null;
	$: offerPair =
		selection?.kind === 'edge' && !showingPair && !worksLoading && selectedPapers.length === 0;
	$: displayPapers = showingPair ? (pairPapers ?? []) : selectedPapers;
	$: displayEntityAtts = showingPair ? pairEntityAtts : $works.entityAtts;
	$: displayTitle =
		showingPair && selection?.kind === 'edge'
			? `${authors[selection.i].name} & ${authors[selection.j].name}`
			: selectionTitle;

	async function loadPair() {
		if (selection?.kind !== 'edge') return;
		const idA = nodeIds[selection.i];
		const idB = nodeIds[selection.j];
		if (!idA || !idB) return;
		pairLoading = true;
		pairError = false;
		const res = await fetchWorkIntersection(
			[
				{ etype: 'authors', ids: [idA] },
				{ etype: 'authors', ids: [idB] }
			],
			200
		);
		pairLoading = false;
		if (!res) {
			pairError = true;
			return;
		}
		pairPapers = res.resp.papers;
		pairEntityAtts = res.resp.entityAtts;
		pairTotal = res.totalPapers;
	}

	function selectNode(i: number) {
		selection = selection?.kind === 'node' && selection.i === i ? null : { kind: 'node', i };
	}
	function selectEdge(i: number, j: number) {
		selection =
			selection?.kind === 'edge' && selection.i === i && selection.j === j
				? null
				: { kind: 'edge', i, j };
	}
	function onKey(e: KeyboardEvent, fn: () => void) {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			fn();
		}
	}

	function nodeActive(k: number, f: Selection): boolean {
		if (f === null) return true;
		if (f.kind === 'node') return f.i === k;
		return f.i === k || f.j === k;
	}
	function edgeActive(a: number, b: number, f: Selection): boolean {
		if (f === null) return true;
		if (f.kind === 'node') return f.i === a || f.i === b;
		return (f.i === a && f.j === b) || (f.i === b && f.j === a);
	}

	function getWeight(i: number, j: number) {
		const idx = getIndex(i, j, n);
		if (idx < 0 || idx >= edgeWeights.length) return 0;
		return edgeWeights[idx] || 0;
	}
	function lastWord(word: string) {
		const words = word.split(' ');
		return words[words.length - 1];
	}
	function scaledNodeScalars(weights: number[]) {
		if (weights.length === 0) return [];
		const maxW = Math.max(...weights);
		return weights.map((e) => e / (maxW * 1.2) + 0.2);
	}
	function paperHref(p: Paper): string | null {
		return p.doi ? `https://doi.org/${p.doi}` : null;
	}
	function edgePath(a: { x: number; y: number }, b: { x: number; y: number }, curve: number) {
		if (!curve) return `M${a.x} ${a.y}L${b.x} ${b.y}`;
		const dx = b.x - a.x;
		const dy = b.y - a.y;
		const len = Math.hypot(dx, dy);
		if (len === 0) return `M${a.x} ${a.y}L${b.x} ${b.y}`;
		const off = len * curve;
		const cx = (a.x + b.x) / 2 - (dy / len) * off;
		const cy = (a.y + b.y) / 2 + (dx / len) * off;
		return `M${a.x} ${a.y}Q${cx} ${cy} ${b.x} ${b.y}`;
	}

	let idealEdgeLength = 100;
	let nodeRepulsion = 4000;
	let edgeElasticity = 100;
	let nestingFactor = 1.2;
	let gravity = 0.05;
	let numIter = 100;
	let initialTemp = 1000;
	let coolingFactor = 0.99;
	let minTemp = 1;

	let positions: { x: number; y: number }[] = [];
	let svgWidth: number;
	let svgHeight: number;

	const marge = 0.09;
	const height = 400;
	const margify = (x: number) => x * (1 + 2 * marge);
	// While the graph is hidden (timeline tab) the clientHeight bind reports 0, so guard the ratio:
	// an unguarded `x/0` yields NaN and paints `MNaN` paths until the ResizeObserver re-fires.
	$: width = svgWidth && svgHeight ? (height * svgWidth) / svgHeight : height;
	$: r = Math.min(14, width / 20);
	$: viewBox = `-${width * marge} -${height * marge} ${margify(width)} ${margify(height)}`;

	$: options = {
		height,
		width,
		idealEdgeLength,
		nodeRepulsion,
		edgeElasticity,
		nestingFactor,
		gravity,
		numIter,
		initialTemp,
		coolingFactor,
		minTemp
	};

	// cytoscape + fcose are heavy; load them lazily and fall back to the circle
	// layout until they arrive (also keeps the force layout off the SSR path)
	let forceLayout: typeof cytoscapeLayout | undefined;
	onMount(() => {
		import('$lib/network-force').then((m) => (forceLayout = m.cytoscapeLayout));
	});
	const possFuns = ['force', 'circle'] as const;
	let actFun: (typeof possFuns)[number] = 'force';
	$: layoutFun = actFun === 'force' && forceLayout ? forceLayout : circleLayout;
	$: positions = safePositions(layoutFun, nodeIds, edgeWeights, options);
	// Bow the edges in free layouts; keep them straight chords on the circle.
	$: edgeCurve = layoutFun === circleLayout ? 0 : 0.15;
	let showControls = false;

	// The force layout can throw (cytoscape on bad data) or return non-finite coords; never let that
	// break the graph — fall back to the always-valid circle layout so a render is guaranteed.
	function safePositions(
		fn: (ids: string[], weights: number[], opts: typeof options) => { x: number; y: number }[],
		ids: string[],
		weights: number[],
		opts: typeof options
	) {
		let p: { x: number; y: number }[] = [];
		try {
			p = fn(ids, weights, opts);
		} catch {
			p = [];
		}
		const ok =
			p.length === ids.length && p.every((c) => Number.isFinite(c?.x) && Number.isFinite(c?.y));
		return ok ? p : circleLayout(ids, weights, opts);
	}
</script>

{#if n === 0}
	<p class="empty">No co-authors to show.</p>
{:else}
	<div class="net">
		<header class="net-head">
			<div class="net-head-top">
				<h3>Co-authors</h3>
				<div class="view-toggle">
					<button
						class="toggle-btn"
						class:active={view === 'network'}
						aria-pressed={view === 'network'}
						on:click={() => (view = 'network')}>network</button
					>
					<button
						class="toggle-btn"
						class:active={view === 'timeline'}
						aria-pressed={view === 'timeline'}
						on:click={() => (view = 'timeline')}>timeline</button
					>
				</div>
			</div>
			{#if view === 'network'}
				<p class="net-sub">
					The {n} scholars most cited alongside <strong>{rootName}</strong>, linked wherever they
					have co-authored with each other. Click a name or a connecting line to browse the papers
					they share.
				</p>
			{:else}
				<p class="net-sub">
					Every collaborator across <strong>{rootName}</strong>'s works, placed by the years they
					published together — including recent or minor co-authors the network leaves out. Raise
					the threshold to focus on closer collaborators; marks flag hit papers, hover for details.
				</p>
			{/if}
		</header>

		{#if view === 'network'}
			<div class="graph-wrap" bind:clientWidth={svgWidth} bind:clientHeight={svgHeight}>
				{#if svgWidth && svgHeight}
					<svg {viewBox} role="img" aria-label="Co-authorship network" transition:fade>
						{#each Array(n) as _, i (i)}
							{#each Array(n) as _, j (j)}
								{#if j > i && getWeight(i, j) > 0}
									{@const w = getWeight(i, j)}
									{@const active = edgeActive(i, j, focus)}
									<path
										class="hit"
										d={edgePath(positions[i], positions[j], edgeCurve)}
										role="button"
										tabindex="-1"
										aria-label={`Papers shared by ${authors[i].name} and ${authors[j].name}`}
										on:click={() => selectEdge(i, j)}
										on:keydown={(e) => onKey(e, () => selectEdge(i, j))}
										on:mouseenter={() => (hovered = { kind: 'edge', i, j })}
										on:mouseleave={() => (hovered = null)}
									/>
									<path
										class="edge"
										class:active={!!focus && active}
										class:dim={focus && !active}
										d={edgePath(positions[i], positions[j], edgeCurve)}
										stroke-width={Math.min(r / 2, 1 + Math.sqrt(w))}
										stroke-opacity={Math.max(0.25, Math.min(0.95, 0.25 + 0.15 * Math.log1p(w)))}
									/>
								{/if}
							{/each}
						{/each}

						{#each authors as a, i (i)}
							{@const active = nodeActive(i, focus)}
							{@const sel = selection?.kind === 'node' && selection.i === i}
							{@const label = lastWord(a.name)}
							{@const labelW = label.length * 7 + 8}
							<g
								class="node"
								class:active={!!focus && active}
								class:dim={focus && !active}
								class:sel
								transform="translate({positions[i].x},{positions[i].y})"
								role="button"
								tabindex="0"
								aria-label={`Papers by ${rootName} and ${a.name}`}
								on:click={() => selectNode(i)}
								on:keydown={(e) => onKey(e, () => selectNode(i))}
								on:mouseenter={() => (hovered = { kind: 'node', i })}
								on:mouseleave={() => (hovered = null)}
							>
								<ellipse rx={r} ry={r} stroke-width={(nodeScales[i] || 1) * 1.8} />
								<rect
									class="label-bg"
									x={-labelW / 2}
									y={r * 0.3 - 11}
									width={labelW}
									height={15}
									rx={2}
								/>
								<text text-anchor="middle" font-size="12" y={r * 0.3}>{label}</text>
							</g>
						{/each}
					</svg>
				{/if}

				<button
					class="gear"
					class:on={showControls}
					aria-label="Layout controls"
					on:click={() => (showControls = !showControls)}>⚙</button
				>
				{#if showControls}
					<div class="controls" transition:slide>
						<label class="ctl">
							<span>Layout</span>
							<select bind:value={actFun}>
								{#each possFuns as name, __i (__i)}<option value={name}>{name}</option>{/each}
							</select>
						</label>
						{#if actFun === 'force'}
							<label class="ctl"
								><span>Gravity {gravity}</span><input
									type="range"
									min="0"
									max="1"
									step="0.01"
									bind:value={gravity}
								/></label
							>
							<label class="ctl"
								><span>Iterations {numIter}</span><input
									type="range"
									min="1"
									max="1000"
									step="1"
									bind:value={numIter}
								/></label
							>
							<label class="ctl"
								><span>Initial temp {initialTemp}</span><input
									type="range"
									min="10"
									max="2000"
									step="1"
									bind:value={initialTemp}
								/></label
							>
							<label class="ctl"
								><span>Cooling {coolingFactor}</span><input
									type="range"
									min="0"
									max="1"
									step="0.01"
									bind:value={coolingFactor}
								/></label
							>
							<label class="ctl"
								><span>Min temp {minTemp}</span><input
									type="range"
									min="1"
									max="1000"
									step="1"
									bind:value={minTemp}
								/></label
							>
						{/if}
					</div>
				{/if}
			</div>

			<div class="legend">
				<span class="lg"><span class="sw sw-node"></span>Border = papers with {rootName}</span>
				<span class="lg"><span class="sw sw-edge"></span>Line = papers co-authored together</span>
				<span class="lg muted">{rootName} links everyone, so they are left out of the graph.</span>
			</div>

			{#if selection}
				<section class="drawer" transition:slide>
					<header class="drawer-head">
						<div class="drawer-titles">
							<span class="kicker">Shared papers</span>
							<h4>{displayTitle}</h4>
						</div>
						<div class="drawer-tools">
							<span class="count"
								>{showingPair ? pairTotal : displayPapers.length}{!showingPair && worksLoading
									? '+'
									: ''}</span
							>
							<button class="close" aria-label="Close" on:click={() => (selection = null)}>✕</button
							>
						</div>
					</header>

					{#if offerPair && selection.kind === 'edge'}
						<div class="offer">
							<p class="status">
								{rootName} has no paper co-authored with both {authors[selection.i].name} and {authors[
									selection.j
								].name}.
							</p>
							{#if pairError}
								<p class="status thin">Couldn't load their shared papers.</p>
							{/if}
							<button class="offer-btn" disabled={pairLoading} on:click={loadPair}>
								{pairLoading
									? 'Loading…'
									: `Show ${authors[selection.i].name} & ${authors[selection.j].name}'s own shared papers`}
							</button>
						</div>
					{:else if displayPapers.length === 0}
						<p class="status">
							{!showingPair && worksLoading
								? `Loading works… (${$works.sliceEnd} of ${$works.totalPapers})`
								: 'No shared papers found.'}
						</p>
					{:else}
						{#if !showingPair && worksLoading}
							<p class="status thin">Loading works… ({$works.sliceEnd} of {$works.totalPapers})</p>
						{/if}
						<ul class="papers">
							{#each displayPapers as p (p.wid)}
								{@const journal = resolveSourceName(p.source, displayEntityAtts)}
								{@const href = paperHref(p)}
								<li class="paper">
									<div class="p-main">
										<div class="p-title">
											{#if href}<a {href} target="_blank" rel="noopener">{@html p.name}</a
												>{:else}{@html p.name}{/if}{#if p.hitSemId}<a
													class="p-breakdown"
													href="/hit-papers/{p.hitSemId}">breakdown →</a
												>{/if}
										</div>
										{#if journal}<div class="p-journal">{journal}</div>{/if}
									</div>
									<div class="p-meta">
										<span class="p-year">{p.year}</span>
										<span class="p-cites">{p.citations.toLocaleString()} cites</span>
									</div>
								</li>
							{/each}
						</ul>
					{/if}
				</section>
			{/if}
		{:else}
			<AuthorTimeline {works} {heroSemanticId} {rootName} />
		{/if}
	</div>
{/if}

<style>
	.net {
		--accent: var(--color-theme-blue, #3b82f6);
		--accent-soft: rgba(var(--color-range-40), 0.28);
		--node-fill: var(--text-bg-2, #eee);
		--node-stroke: rgb(var(--color-range-20));
		--edge-color: rgba(var(--color-range-40), 0.8);
		--hair: rgba(var(--color-range-15), 0.12);
		display: flex;
		flex-direction: column;
		gap: 16px;
		width: 100%;
	}

	@media (prefers-color-scheme: dark) {
		.net {
			--edge-color: rgb(var(--color-range-95));
			--node-fill: rgba(var(--color-range-15), 0.22);
		}
	}

	.net-head-top {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 12px;
		margin-bottom: 4px;
	}

	.net-head h3 {
		margin: 0;
	}

	.view-toggle {
		display: flex;
		gap: 2px;
		flex-shrink: 0;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		border-radius: var(--control-bar-pill-radius);
		overflow: hidden;
	}

	.toggle-btn {
		background: none;
		border: none;
		font-family: inherit;
		font-size: var(--control-bar-font);
		padding: var(--control-bar-pill-pad);
		cursor: pointer;
		color: inherit;
		opacity: 0.5;
		transition:
			opacity 0.15s,
			background 0.15s;
	}

	.toggle-btn.active {
		opacity: 1;
		background: rgba(var(--color-range-15), 0.1);
	}

	.net-sub {
		margin: 0;
		max-width: 72ch;
		font-size: var(--text-sm);
		line-height: 1.55;
		opacity: 0.72;
	}

	.net-sub strong {
		font-weight: 600;
		opacity: 1;
	}

	.graph-wrap {
		position: relative;
		width: 100%;
		height: min(66svh, 92vw);
		border: 1px solid var(--hair);
		border-radius: 12px;
		background: radial-gradient(
			circle at 50% 38%,
			rgba(var(--color-range-30), 0.07),
			transparent 72%
		);
		overflow: hidden;
	}

	svg {
		width: 100%;
		height: 100%;
		display: block;
	}

	.edge {
		fill: none;
		stroke: var(--edge-color);
		pointer-events: none;
		transition: stroke-opacity 0.15s ease;
	}

	.edge.active {
		stroke-opacity: 1 !important;
	}

	.edge.dim {
		stroke-opacity: 0.07 !important;
	}

	.hit {
		fill: none;
		stroke: transparent;
		stroke-width: 16;
		cursor: pointer;
		outline: none;
	}

	.node {
		cursor: pointer;
		outline: none;
		transition: opacity 0.15s ease;
	}

	.node ellipse {
		fill: var(--node-stroke);
		fill-opacity: 0.32;
		stroke: var(--node-stroke);
		transition:
			fill 0.15s ease,
			stroke 0.15s ease;
	}

	.label-bg {
		fill: var(--text-bg, #fff);
		fill-opacity: 0.9;
		filter: blur(3px);
		pointer-events: none;
	}

	.node text {
		fill: var(--color-text);
		font-weight: 100;
		pointer-events: none;
		user-select: none;
	}

	.node:hover ellipse,
	.node.active ellipse,
	.node:focus-visible ellipse {
		stroke: var(--accent);
	}

	.node.sel ellipse {
		fill: var(--accent-soft);
		stroke: var(--accent);
	}

	.node.dim {
		opacity: 0.3;
	}

	.gear {
		position: absolute;
		top: 10px;
		right: 10px;
		width: 32px;
		height: 32px;
		display: grid;
		place-items: center;
		border: 1px solid var(--hair);
		border-radius: 8px;
		background: rgba(var(--color-range-15), 0.06);
		color: var(--color-text);
		cursor: pointer;
		font-size: 0.95rem;
		line-height: 1;
		transition:
			background 0.15s ease,
			opacity 0.15s ease;
	}

	.gear:hover,
	.gear.on {
		background: rgba(var(--color-range-15), 0.14);
	}

	.controls {
		position: absolute;
		top: 50px;
		right: 10px;
		z-index: 2;
		width: min(264px, 84%);
		padding: 12px 14px;
		display: flex;
		flex-direction: column;
		gap: 10px;
		background: var(--text-bg, #fff);
		border: 1px solid var(--hair);
		border-radius: 10px;
		box-shadow: 0 8px 28px rgba(0, 0, 0, 0.18);
	}

	.ctl {
		display: flex;
		flex-direction: column;
		gap: 4px;
		font-size: var(--text-xs);
		opacity: 0.85;
	}

	.ctl input[type='range'] {
		width: 100%;
	}

	.ctl select {
		font: inherit;
	}

	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: 6px 20px;
		font-size: var(--text-xs);
		opacity: 0.85;
	}

	.lg {
		display: inline-flex;
		align-items: center;
		gap: 7px;
	}

	.lg.muted {
		opacity: 0.62;
		font-style: italic;
	}

	.sw {
		flex-shrink: 0;
		display: inline-block;
	}

	.sw-node {
		width: 15px;
		height: 15px;
		border-radius: 50%;
		border: 3px solid var(--node-stroke);
		background: var(--node-fill);
	}

	.sw-edge {
		width: 20px;
		height: 0;
		border-top: 3px solid var(--edge-color);
	}

	.drawer {
		border: 1px solid var(--hair);
		border-radius: 12px;
		overflow: hidden;
	}

	.drawer-head {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 12px;
		padding: 12px 16px;
		background: rgba(var(--color-range-15), 0.04);
		border-bottom: 1px solid var(--hair);
	}

	.kicker {
		font-size: var(--text-xs);
		text-transform: uppercase;
		letter-spacing: 0.06em;
		opacity: 0.5;
	}

	.drawer-titles h4 {
		margin: 3px 0 0;
		font-size: var(--text-base);
		line-height: 1.25;
	}

	.drawer-tools {
		display: flex;
		align-items: center;
		gap: 10px;
		flex-shrink: 0;
	}

	.count {
		font-variant-numeric: tabular-nums;
		font-size: var(--text-sm);
		opacity: 0.6;
	}

	.close {
		background: none;
		border: none;
		color: inherit;
		cursor: pointer;
		font-size: 0.95rem;
		opacity: 0.55;
		padding: 2px;
		line-height: 1;
	}

	.close:hover {
		opacity: 1;
	}

	.status {
		margin: 0;
		padding: 16px;
		text-align: center;
		font-size: var(--text-sm);
		opacity: 0.6;
	}

	.status.thin {
		padding: 8px 16px;
		opacity: 0.5;
	}

	.offer {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 10px;
		padding: 16px;
		text-align: center;
	}

	.offer .status {
		padding: 0;
	}

	.offer-btn {
		font: inherit;
		font-size: var(--text-sm);
		padding: 8px 14px;
		border: 1px solid var(--accent);
		border-radius: 8px;
		background: var(--accent-soft);
		color: var(--color-text);
		cursor: pointer;
		transition: background 0.15s ease;
	}

	.offer-btn:hover:not(:disabled) {
		background: rgba(var(--color-range-40), 0.42);
	}

	.offer-btn:disabled {
		opacity: 0.6;
		cursor: default;
	}

	.papers {
		list-style: none;
		margin: 0;
		padding: 4px 0;
		max-height: 380px;
		overflow-y: auto;
	}

	.paper {
		display: flex;
		justify-content: space-between;
		gap: 14px;
		padding: 9px 16px;
		border-bottom: 1px solid rgba(var(--color-range-15), 0.06);
	}

	.paper:last-child {
		border-bottom: none;
	}

	.p-main {
		min-width: 0;
	}

	.p-title {
		font-size: var(--text-sm);
		line-height: 1.35;
		overflow-wrap: anywhere;
	}

	.p-title a {
		color: inherit;
		text-decoration: none;
	}

	.p-title a:hover {
		text-decoration: underline;
	}

	.p-breakdown {
		margin-left: 7px;
		font-size: var(--text-xs);
		white-space: nowrap;
		opacity: 0.7;
	}

	.p-journal {
		margin-top: 2px;
		font-size: var(--text-xs);
		font-style: italic;
		opacity: 0.58;
	}

	.p-meta {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 2px;
		flex-shrink: 0;
		font-variant-numeric: tabular-nums;
	}

	.p-year {
		font-size: var(--text-sm);
		opacity: 0.8;
	}

	.p-cites {
		font-size: var(--text-xs);
		white-space: nowrap;
		opacity: 0.55;
	}

	.empty {
		opacity: 0.6;
	}

	@media (min-width: 1200px) {
		.net-sub,
		.p-title,
		.drawer-titles h4 {
			font-size: var(--text-base);
		}
	}
</style>
