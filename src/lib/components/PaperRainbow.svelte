<script lang="ts">
	import { LATEST_YEAR } from '$lib/constants';
	import { getColor, getColorArr } from '$lib/style-util';
	import { formatNumber } from '$lib/text-format-util';
	import type * as tt from '$lib/tree-types';
	import * as tf from '$lib/tree-functions';
	import { resolveSourceName } from '$lib/utils/paper-helpers';
	import {
		computeYearRates,
		getFigureBasis,
		getVisInds,
		rainbowPapers,
		tipLabelPos,
		xBase,
		type RainbowSort
	} from '$lib/utils/paper-rainbow';
	import AuthorList from './AuthorList.svelte';
	import HitPaperBreakdown from './HitPaperBreakdown.svelte';
	import HitPaperExplainer from './HitPaperExplainer.svelte';
	import { onMount, tick } from 'svelte';

	export let papers: tt.Paper[];
	export let entityAtts: tt.EntityAttsForLinks = {};
	export let discAuthorNames: Record<string, string> = {};
	export let treeSpecs: tt.TreeSpecs | undefined = undefined;

	const fontSize = 0.5;

	type BreakdownOption = { key: string; label: string; treeId: number };

	let maxN = 15;
	let highlighted = 0;
	let alignTrajectories = true;
	let logScale = false;
	let sortBy: RainbowSort = 'year';
	let viewMode: 'lines' | 'breakdown' = 'lines';

	let breakdownTreeId = 0;
	let breakdownIsSpec = false;

	let expandedSet: Set<number> = new Set();
	let listContainer: HTMLUListElement;
	let listItemElements: HTMLLIElement[] = [];
	let firstVisible: number | null = null;
	let scrollTimeout: ReturnType<typeof setTimeout>;

	function getBreakdownOptionsList(specs: tt.TreeSpecs | undefined): BreakdownOption[] {
		if (!specs) return [];
		const hpSpecs = specs.specs['hit-papers'];
		if (!hpSpecs) return [];
		const bdOptions = tf.getBreakdownOptions(specs, 'hit-papers', 1);
		const opts: BreakdownOption[] = [];
		for (const [key, val] of Object.entries(bdOptions)) {
			if (val.treeSpecs.length === 0) continue;
			const etype = key.split('-')[0];
			opts.push({ key, label: etype, treeId: val.treeSpecs[0] });
		}
		return opts;
	}

	function fixHighlight(i: number) {
		highlighted = i;
	}

	function switchToBreakdown() {
		viewMode = 'breakdown';
	}

	function switchToLines() {
		viewMode = 'lines';
	}

	function getLiStyle(i: number, visInds: number[], hl: number, rate: number) {
		if (!visInds.includes(i)) return '';
		const ext = hl === i ? '0.4); box-shadow: 3px 3px 10px var(--color-theme-shadow);' : '0.2)';
		return `background-color: rgba(${getColorArr(rate)}, ${ext}`;
	}

	// The chart window follows the list: it starts at the topmost item still touching the viewport's top
	// edge. Crucially this never returns null — requiring a *fully* visible item meant that once an item
	// (e.g. an expanded one) grew taller than the scroll box, no item qualified and the window snapped
	// back to the top, yanking the highlight up and making the lowest papers unreachable.
	function updateFirstVisible(): void {
		if (!listContainer || listItemElements.length === 0) return;
		const top = listContainer.getBoundingClientRect().top;
		let idx = listItemElements.length - 1;
		for (let k = 0; k < listItemElements.length; k++) {
			if (listItemElements[k].getBoundingClientRect().bottom > top + 4) {
				idx = k;
				break;
			}
		}
		firstVisible = idx;
	}

	function onScrollDebounced() {
		clearTimeout(scrollTimeout);
		scrollTimeout = setTimeout(updateFirstVisible, 50);
	}

	async function toggleExpand(i: number) {
		const next = new Set(expandedSet);
		if (next.has(i)) next.delete(i);
		else next.add(i);
		expandedSet = next;
		// Expanding/collapsing changes item heights, so realign the chart window with what's now on screen.
		await tick();
		updateFirstVisible();
	}

	onMount(() => {
		listItemElements = Array.from(listContainer.querySelectorAll('li[data-index]'));
		listContainer.addEventListener('scroll', onScrollDebounced);
		updateFirstVisible();
	});

	$: breakdownOptions = getBreakdownOptionsList(treeSpecs);

	$: if (
		breakdownOptions.length > 0 &&
		!breakdownOptions.find((o) => o.treeId === breakdownTreeId)
	) {
		breakdownTreeId = breakdownOptions[0].treeId;
	}

	$: breakdownTreeSpec =
		treeSpecs && treeSpecs.specs['hit-papers']
			? treeSpecs.specs['hit-papers'][breakdownTreeId]
			: undefined;

	$: chartPapers = rainbowPapers(papers, sortBy);

	$: paperCap = Math.min(200, chartPapers.length);
	$: if (maxN > paperCap) maxN = paperCap;

	$: rates = computeYearRates(chartPapers);
	$: visInds = getVisInds(chartPapers, firstVisible ?? 0, maxN);
	$: visMinYear =
		visInds.length > 0 ? Math.min(...visInds.map((i) => chartPapers[i].year)) : LATEST_YEAR - 1;
	$: fb = getFigureBasis(chartPapers, visInds, visMinYear, alignTrajectories, rates, logScale);
	$: highlightedVis = visInds.includes(highlighted) ? highlighted - visInds[0] : undefined;
</script>

<div class="rainbow-wrap">
	{#if chartPapers.length > 0}
		<div class="chart-area">
			<div class="chart-controls">
				<div class="view-toggle">
					<button class="toggle-btn" class:active={viewMode === 'lines'} on:click={switchToLines}
						>citation timeline</button
					>
					<button
						class="toggle-btn"
						class:active={viewMode === 'breakdown'}
						on:click={switchToBreakdown}>citation breakdown</button
					>
				</div>
				{#if viewMode === 'lines'}
					{#if paperCap > 4}
						<label>
							<input type="range" min="4" max={paperCap} bind:value={maxN} />
							{maxN} papers
						</label>
					{/if}
					<label>
						<input type="checkbox" bind:checked={alignTrajectories} />
						align trajectories
					</label>
					<label>
						<input type="checkbox" bind:checked={logScale} />
						log scale
					</label>
					<select bind:value={sortBy} class="breakdown-select" aria-label="Sort by">
						<option value="citations">sort: citations</option>
						<option value="score">sort: paper score</option>
						<option value="year">sort: publication year</option>
					</select>
				{:else if breakdownOptions.length > 0}
					<select bind:value={breakdownTreeId} class="breakdown-select" aria-label="Breakdown type">
						{#each breakdownOptions as opt, __i (__i)}
							<option value={opt.treeId}>{opt.label}</option>
						{/each}
					</select>
					<label>
						<input type="checkbox" bind:checked={breakdownIsSpec} />
						specialization
					</label>
				{/if}
			</div>
			{#if viewMode === 'breakdown'}
				{@const hp = chartPapers[highlighted]}
				{#if hp?.hitSemId}
					<div class="breakdown-view" style="aspect-ratio: {fb.aspect.toFixed(3)};">
						<HitPaperBreakdown
							semanticId={hp.hitSemId}
							treeId={breakdownTreeId}
							isSpec={breakdownIsSpec}
							treeSpec={breakdownTreeSpec}
							aspectRatio={fb.aspect}
						/>
						<a href="/hit-papers/{hp.hitSemId}" class="profile-link">full profile →</a>
					</div>
				{:else}
					<p class="no-breakdown">No breakdown available for this paper.</p>
				{/if}
			{:else}
				<div class="plot">
					{#if highlightedVis !== undefined}
						{@const hp = fb.figPapers[highlightedVis]}
						<div class="chart-title">
							{#if hp.doi.length > 0}
								<a href="https://doi.org/{hp.doi}" target="_blank" rel="noopener">{@html hp.name}</a
								>
							{:else}
								<span>{@html hp.name}</span>
							{/if}
							<span class="chart-title-meta"
								>{hp.year} · {formatNumber(hp.citations)} citations</span
							>
						</div>
					{/if}
					<svg
						viewBox="{fb.xMin} {fb.yMin} {fb.width} {fb.height}"
						style="aspect-ratio: {fb.aspect.toFixed(3)};"
					>
						<!-- Y-axis grid lines -->
						<g stroke="var(--color-text)" stroke-width="0.015" opacity="0.15">
							{#each fb.yTicks as tick, __i (__i)}
								<line x1="0" y1={tick.y} x2={xBase} y2={tick.y} />
							{/each}
						</g>

						<!-- Paper citation lines (cumulative). Drawn decoratively; the wide transparent hit
						     paths below carry the pointer events so the thin lines stay tappable on touch. -->
						{#each fb.figPapers as paper, __i (__i)}
							<path
								class="cite-line"
								fill="none"
								stroke={getColor(paper.rate)}
								stroke-width={paper.i === highlighted ? 0.18 : 0.1}
								stroke-linecap="round"
								stroke-linejoin="round"
								d={paper.path}
								opacity={paper.i === highlighted ? 1.0 : 0.4}
								id="hit-paper-path-{paper.i}"
							/>
						{/each}
						{#each fb.figPapers as paper, __i (__i)}
							<path
								class="hit-line"
								role="region"
								fill="none"
								stroke="transparent"
								stroke-width="0.8"
								stroke-linecap="round"
								d={paper.path}
								on:mouseover={() => fixHighlight(paper.i)}
								on:focus={() => fixHighlight(paper.i)}
							/>
						{/each}

						<!-- Total cites for the highlighted paper sit at its line tip (name moved to top-left) -->
						{#if highlightedVis !== undefined}
							{@const hp = fb.figPapers[highlightedVis]}
							{@const pos = tipLabelPos(hp)}
							<text
								x={pos.x}
								y={pos.y}
								font-size="0.5"
								font-weight="600"
								text-anchor={pos.anchor}
								fill={getColor(hp.rate)}>{formatNumber(hp.citations)}</text
							>
						{/if}

						<!-- X axis baseline and ticks -->
						<g
							stroke-width="0.03"
							stroke="var(--color-text)"
							fill="var(--color-text)"
							font-size={fontSize}
						>
							<path d="M 0 0 h {xBase}" />
							{#each fb.yearTicks as tick, __i (__i)}
								<path d="M {tick.x} 0 v 0.35" />
								{#if tick.name !== undefined}
									<text x={tick.x} y="0.9" text-anchor="middle">{tick.name}</text>
								{/if}
							{/each}
						</g>

						<!-- X axis title (offset axis is only meaningful when trajectories are aligned) -->
						{#if fb.align}
							<text
								x={xBase / 2}
								y="2"
								text-anchor="middle"
								font-size="0.7"
								fill="var(--color-text)"
								opacity="0.6">Years since publication</text
							>
						{/if}

						<!-- Paper publication markers (only when x is calendar-aligned) -->
						{#if !fb.align}
							{#each fb.pubMarks as mark, __i (__i)}
								<line
									x1={mark.x}
									y1="0"
									x2={mark.x}
									y2="0.45"
									stroke={mark.color}
									stroke-width="0.09"
								/>
							{/each}
						{/if}

						<!-- Y-axis ticks and labels -->
						<g fill="var(--color-text)" font-size="0.65">
							{#each fb.yTicks as tick, __i (__i)}
								<line
									x1={xBase}
									y1={tick.y}
									x2={xBase + 0.4}
									y2={tick.y}
									stroke="var(--color-text)"
									stroke-width="0.025"
								/>
								<text x={xBase + 0.55} y={tick.y + 0.15} text-anchor="start">{tick.label}</text>
							{/each}
						</g>
					</svg>
				</div>
			{/if}
		</div>
	{/if}

	<div class="sidebar">
		<HitPaperExplainer />

		<ol id="paper-list" bind:this={listContainer}>
			{#each chartPapers as paper, i (i)}
				{@const source = resolveSourceName(paper.source, entityAtts)}
				{@const expanded = expandedSet.has(i)}
				<li
					style={getLiStyle(i, visInds ?? [], highlighted, rates[i])}
					data-index={i}
					on:mouseover={() => fixHighlight(i)}
					on:focus={() => fixHighlight(i)}
				>
					<div
						class="paper-block"
						role="button"
						tabindex="0"
						on:click={() => toggleExpand(i)}
						on:keydown={(e) => {
							if (e.key === 'Enter' || e.key === ' ') {
								e.preventDefault();
								toggleExpand(i);
							}
						}}
					>
						<div class="paper-collapsed">
							<span class="paper-year">{paper.year}</span>
							{#if source}
								<span class="paper-source">{source}</span>
							{:else}
								<span class="paper-source paper-source-fallback">{@html paper.name}</span>
							{/if}
						</div>
						{#if expanded}
							<div class="paper-expanded">
								<div class="paper-title">
									{#if paper.doi.length > 0}
										<a
											href="https://doi.org/{paper.doi}"
											target="_blank"
											on:click|stopPropagation={() => {}}>{@html paper.name}</a
										>
									{:else}
										{@html paper.name}
									{/if}
								</div>
								<div class="paper-meta">
									<span class="paper-cites">{formatNumber(paper.citations)} citations</span>
									{#if paper.authorships.length}<span class="paper-authors"
											><AuthorList {paper} {entityAtts} {discAuthorNames} max={2} /></span
										>{/if}
									{#if paper.createdTopic}
										<span class="paper-created-topic" title="Earliest impactful paper of this topic"
											>★ originated {@html paper.createdTopic}</span
										>
									{/if}
									{#if paper.hitSemId}
										<a
											href="/hit-papers/{paper.hitSemId}"
											class="paper-profile-link"
											on:click|stopPropagation={() => {}}>profile →</a
										>
									{/if}
								</div>
								<div class="paper-details">
									{#if paper.authorships.length > 2}
										<div class="detail-row">
											<span class="detail-label">Authors:</span>
											<span><AuthorList {paper} {entityAtts} {discAuthorNames} showInst /></span>
										</div>
									{/if}
									{#if paper.biblio}
										{@const b = paper.biblio}
										<div class="detail-row">
											<span class="detail-label">Published in:</span>
											<span>
												{#if b.volume}Vol.&nbsp;{b.volume}{/if}{#if b.issue}, No.&nbsp;{b.issue}{/if}{#if b.first_page},
													pp.&nbsp;{b.first_page}{#if b.last_page}–{b.last_page}{/if}{/if}
											</span>
										</div>
									{/if}
									{#if paper.score !== undefined && paper.bar !== undefined}
										<div class="detail-row selection-basis">
											<span class="detail-label">Paper score:</span>
											<span
												>{paper.score.toFixed(2)} (bar: {formatNumber(paper.bar)} citations)</span
											>
										</div>
									{/if}
								</div>
							</div>
						{/if}
					</div>
				</li>
			{/each}
		</ol>
	</div>
</div>

<style>
	.rainbow-wrap {
		display: flex;
		flex-direction: column;
		gap: 16px;
	}

	.chart-area {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}

	/* The rising trajectories leave the plot's top-left empty, so the highlighted paper's full title
	   lives there (wrapping freely) instead of being squeezed onto the line. */
	.plot {
		position: relative;
	}

	.chart-title {
		position: absolute;
		top: 0;
		left: 0;
		max-width: 58%;
		font-size: var(--text-sm);
		font-weight: 600;
		line-height: 1.25;
		/* Let line hovering through the empty region; only the DOI link itself is clickable. */
		pointer-events: none;
	}

	.chart-title a {
		pointer-events: auto;
		color: var(--color-text);
	}

	.chart-title a:hover {
		text-decoration: underline;
	}

	.chart-title-meta {
		display: block;
		margin-top: 2px;
		font-weight: 400;
		font-size: var(--text-xs);
		opacity: 0.6;
	}

	.chart-controls {
		display: flex;
		gap: 10px;
		flex-wrap: wrap;
		align-items: center;
		font-size: var(--control-bar-font);
		opacity: 0.75;
		padding: var(--control-bar-pad-v) 0;
	}

	.chart-controls label {
		display: flex;
		align-items: center;
		gap: 6px;
		cursor: pointer;
	}

	.view-toggle {
		display: flex;
		gap: 2px;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		border-radius: var(--control-bar-pill-radius);
		overflow: hidden;
		flex-shrink: 0;
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

	.breakdown-select {
		font-family: inherit;
		font-size: var(--control-bar-font);
		padding: var(--control-bar-pill-pad);
		border-radius: var(--control-bar-pill-radius);
		border: 1px solid rgba(var(--color-range-15), 0.2);
		background: none;
		color: inherit;
		cursor: pointer;
	}

	.breakdown-view {
		display: flex;
		flex-direction: column;
		gap: 4px;
		min-height: 280px;
		width: 100%;
	}

	.profile-link {
		font-size: var(--text-sm);
		font-weight: 600;
		color: var(--color-theme-blue);
		text-decoration: none;
		align-self: flex-end;
		opacity: 0.8;
		transition: opacity 0.15s;
	}

	.profile-link:hover {
		opacity: 1;
	}

	.no-breakdown {
		font-size: var(--text-sm);
		opacity: 0.4;
		padding: 20px 0;
		text-align: center;
	}

	.paper-profile-link {
		font-size: var(--text-xs);
		color: var(--color-theme-blue);
		text-decoration: none;
		opacity: 0.6;
		flex-shrink: 0;
		transition: opacity 0.15s;
	}

	.paper-profile-link:hover {
		opacity: 1;
	}

	svg {
		width: 100%;
		min-height: 280px;
		flex: 0;
		/* Kill the black tap-highlight box Chrome paints over an SVG element's bounding box on touch. */
		-webkit-tap-highlight-color: transparent;
	}

	text {
		pointer-events: none;
	}

	svg path {
		outline: none;
	}

	.cite-line {
		pointer-events: none;
		transition:
			opacity 400ms,
			stroke-width 400ms;
	}

	.hit-line {
		cursor: pointer;
	}

	li {
		transition: all 400ms;
	}

	#paper-list {
		min-width: 0;
		padding-top: 0;
		padding-right: 0;
		padding-bottom: 25svh;
		max-height: 55svh;
		overflow-y: scroll;
	}

	#paper-list > li {
		margin-top: 3px;
		font-weight: 600;
	}

	.paper-block {
		padding: 3px 8px;
		cursor: pointer;
	}

	.paper-collapsed {
		display: flex;
		align-items: baseline;
		gap: 8px;
		min-width: 0;
	}

	.paper-expanded {
		margin-top: 5px;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.paper-title {
		font-weight: 600;
		line-height: 1.3;
	}

	.paper-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 4px 12px;
		font-size: var(--text-sm);
		font-weight: 400;
		opacity: 0.65;
	}

	.paper-year {
		font-weight: 600;
		flex-shrink: 0;
	}

	.paper-cites {
		font-weight: 600;
	}

	.paper-source {
		flex: 1;
		min-width: 0;
		font-style: italic;
		font-weight: 400;
		opacity: 0.7;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.paper-source-fallback {
		font-style: normal;
	}

	.paper-created-topic {
		font-weight: 600;
		color: var(--color-theme-blue);
		flex-shrink: 0;
	}

	.paper-details {
		margin-top: 8px;
		font-size: var(--text-sm);
		font-weight: 400;
		border-top: 1px solid rgba(128, 128, 128, 0.3);
		padding-top: 6px;
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.detail-row {
		display: flex;
		gap: 6px;
		flex-wrap: wrap;
	}

	.detail-label {
		opacity: 0.6;
		flex-shrink: 0;
	}

	.selection-basis {
		margin-top: 2px;
		font-style: italic;
		opacity: 0.8;
	}

	@media (min-width: 1100px) {
		.rainbow-wrap {
			flex-direction: row;
			gap: 0;
			align-items: flex-start;
		}

		.chart-area {
			min-width: 600px;
			flex: 8;
		}

		.sidebar {
			flex: 4;
			min-width: 400px;
			padding-top: 40px;
			padding-right: 18px;
		}
	}
</style>
