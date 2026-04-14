<script lang="ts">
	import { LATEST_YEAR } from '$lib/constants';
	import { getColor, getColorArr } from '$lib/style-util';
	import { formatNumber } from '$lib/text-format-util';
	import type * as tt from '$lib/tree-types';
	import * as tf from '$lib/tree-functions';
	import { resolveAuthorNameOrNull, resolveSourceName, stripHtml } from '$lib/utils/paper-helpers';
	import HitPaperBreakdown from './HitPaperBreakdown.svelte';
	import HitPaperExplainer from './HitPaperExplainer.svelte';
	import { onMount } from 'svelte';

	export let papers: tt.Paper[];
	export let entityAtts: tt.EntityAttsForLinks = {};
	export let discAuthorNames: Record<string, string> = {};
	export let treeSpecs: tt.TreeSpecs | undefined = undefined;

	const xPad = 2;
	const yPad = 2.5;
	const xBase = 26;
	const yBase = 12;
	const maxN = 5;
	const fontSize = 0.5;
	const bmThreshold = 5;
	const globalMinCites = 500;
	let highlighted = 0;
	let alignTrajectories = false;
	let sortByOverperf = false;
	let viewMode: 'lines' | 'breakdown' = 'lines';

	let breakdownTreeId = 0;
	let breakdownIsSpec = false;

	type BreakdownOption = { key: string; label: string; treeId: number };

	$: breakdownOptions = getBreakdownOptionsList(treeSpecs);

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

	function overperf(p: tt.Paper): number {
		if (!p.hitBm || p.hitBm < 5) return 0;
		return p.citations / p.hitBm;
	}
	let expandedSet: Set<number> = new Set();

	let listContainer: HTMLUListElement;
	let listItemElements: HTMLLIElement[] = [];
	let firstVisible: number | null = null;
	let scrollTimeout: ReturnType<typeof setTimeout>;

	$: chartPapers = papers
		.filter((p) => p.yearlyCites && p.yearlyCites.length > 0)
		.toSorted((a, b) => (sortByOverperf ? overperf(b) - overperf(a) : b.citations - a.citations));

	$: globalMinYear =
		chartPapers.length > 0 ? Math.min(...chartPapers.map((p) => p.year)) : LATEST_YEAR - 1;

	function getVisInds(ps: tt.Paper[], first: number): number[] {
		const inds: number[] = [];
		for (let i = first; i < Math.min(ps.length, first + maxN); i++) inds.push(i);
		return inds;
	}

	type PubMark = { x: number; year: number; color: string; row: number };
	type YTick = { label: string; y: number };
	type FigPaper = {
		i: number;
		rate: number;
		path: string;
		name: string;
		doi: string;
		endX: number;
		endY: number;
		pathName: string;
		year: number;
		citations: number;
	};

	function niceYTickSteps(yMax: number): number[] {
		const roughStep = yMax / 4;
		const order = Math.floor(Math.log10(roughStep));
		for (const exp of [order + 1, order, order - 1]) {
			const mag = Math.pow(10, exp);
			for (const m of [5, 4, 2.5, 2, 1]) {
				const step = m * mag;
				if (step <= 0) continue;
				const count = Math.floor(yMax / step);
				if (count >= 3 && count <= 5) {
					return Array.from({ length: count }, (_, i) => Math.round((i + 1) * step));
				}
			}
		}
		return [0.25, 0.5, 0.75, 1].map((f) => Math.round(f * yMax));
	}

	function getFigureBasis(ps: tt.Paper[], inds: number[], globalMin: number, align: boolean) {
		const nVis = inds.length;
		const yearSpan = LATEST_YEAR - globalMin;
		const xScale = Math.max(yearSpan - 1, 1) / xBase;

		const width = xBase + xPad + 5;
		const height = yBase + yPad * 2;
		const aspect = width / height;
		const xMin = -xPad;
		const yMin = -height + yPad;

		let yMax = 0;
		for (const i of inds) yMax = Math.max(yMax, ps[i].citations);
		if (yMax === 0) yMax = 1;
		const yScale = yMax / yBase;

		const figPapers: FigPaper[] = [];
		const pubMarks: PubMark[] = [];

		for (let vi = 0; vi < nVis; vi++) {
			const i = inds[vi];
			const paper = ps[i];
			const yc = paper.yearlyCites ?? [];
			const startYear = paper.year - globalMin;
			const lifespan = Math.max(LATEST_YEAR - paper.year, 1);
			const rate = nVis > 1 ? vi / nVis : 0;

			let endX = 0,
				endY = 0;
			let cumSum = 0;
			const pBasis: string[] = [];

			for (let y = 0; y < yc.length && y < lifespan; y++) {
				cumSum += yc[y];
				const xPos = ((align ? 0 : startYear) + y) / xScale;
				const yVal = -(cumSum / yScale);
				endX = xPos;
				endY = yVal;
				pBasis.push(`${y === 0 ? 'M' : 'L'} ${xPos.toFixed(3)} ${yVal.toFixed(3)}`);
			}

			const markerX = align ? 0 : startYear / xScale;
			pubMarks.push({ x: markerX, year: paper.year, color: getColor(rate), row: vi % 2 });

			const plainName = stripHtml(paper.name);
			const pathName = plainName.length > 28 ? plainName.slice(0, 25) + '...' : plainName;

			figPapers.push({
				i,
				rate,
				path: pBasis.join(' '),
				name: paper.name,
				doi: paper.doi,
				endX,
				endY: Math.max(endY, -yBase + 0.8),
				pathName,
				year: paper.year,
				citations: paper.citations
			});
		}

		const yearTicks: { name?: string | number; x: number }[] = [];
		if (align) {
			yearTicks.push({ name: 'pub.', x: 0 });
			for (let i = 1; i < yearSpan - 1; i++) {
				yearTicks.push({ name: '', x: i / xScale });
			}
		} else {
			yearTicks.push({ name: globalMin, x: 0 }, { name: LATEST_YEAR, x: xBase });
			const toT = (i: number, k: number) => i === Math.floor((k * yearSpan) / 3);
			for (let i = 1; i < yearSpan - 1; i++) {
				yearTicks.push({
					name: toT(i, 1) || toT(i, 2) ? globalMin + i : undefined,
					x: i / xScale
				});
			}
		}

		const yTicks: YTick[] = [];
		for (const val of niceYTickSteps(yMax)) {
			yTicks.push({ label: formatNumber(val), y: -(val / yMax) * yBase });
		}

		return { width, height, xMin, yMin, figPapers, yearTicks, yTicks, pubMarks, aspect, align };
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

	function getLiStyle(i: number, visInds: number[], hl: number) {
		if (!visInds.includes(i)) return '';
		const rate = visInds.length > 1 ? (i - visInds[0]) / visInds.length : 0;
		const ext = hl === i ? '0.5); box-shadow: 3px 3px 10px var(--color-theme-shadow);' : '0.3)';
		return `background-color: rgba(${getColorArr(rate)}, ${ext}`;
	}

	function updateFirstVisible(): void {
		const containerRect = listContainer.getBoundingClientRect();
		const fullyVisible = listItemElements
			.map((el, index) => ({ el, index, rect: el.getBoundingClientRect() }))
			.filter(({ rect }) => rect.top >= containerRect.top && rect.bottom <= containerRect.bottom)
			.sort((a, b) => a.rect.top - b.rect.top);
		firstVisible = fullyVisible.length > 0 ? fullyVisible[0].index : null;
	}

	function onScrollDebounced() {
		clearTimeout(scrollTimeout);
		scrollTimeout = setTimeout(updateFirstVisible, 50);
	}

	function shortAuthors(paper: tt.Paper): string {
		if (!paper.authorships?.length) return '';
		const total = paper.authorships.length;
		const known: string[] = [];
		for (const s of paper.authorships) {
			if (known.length >= 2) break;
			const name = resolveAuthorNameOrNull(s, entityAtts, discAuthorNames);
			if (name !== null) known.push(name);
		}
		if (known.length === 0) return `${total} author${total > 1 ? 's' : ''}`;
		return known.join(', ') + (total > known.length ? ' et al.' : '');
	}

	function allAuthors(paper: tt.Paper): string[] {
		return paper.authorships.map(
			(s) => resolveAuthorNameOrNull(s, entityAtts, discAuthorNames) ?? '(unknown)'
		);
	}

	function toggleExpand(i: number) {
		const next = new Set(expandedSet);
		if (next.has(i)) next.delete(i);
		else next.add(i);
		expandedSet = next;
	}

	onMount(() => {
		listItemElements = Array.from(listContainer.querySelectorAll('li[data-index]'));
		listContainer.addEventListener('scroll', onScrollDebounced);
		updateFirstVisible();
	});

	$: visInds = getVisInds(chartPapers, firstVisible ?? 0);
	$: fb = getFigureBasis(chartPapers, visInds, globalMinYear, alignTrajectories);
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
					<label>
						<input type="checkbox" bind:checked={alignTrajectories} />
						align trajectories
					</label>
					<label>
						<input type="checkbox" bind:checked={sortByOverperf} />
						sort by overperformance
					</label>
				{:else if breakdownOptions.length > 0}
					<select bind:value={breakdownTreeId} class="breakdown-select" aria-label="Breakdown type">
						{#each breakdownOptions as opt}
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
				<svg
					viewBox="{fb.xMin} {fb.yMin} {fb.width} {fb.height}"
					style="aspect-ratio: {fb.aspect.toFixed(3)};"
				>
					<!-- Y-axis grid lines -->
					<g stroke="var(--color-text)" stroke-width="0.015" opacity="0.15">
						{#each fb.yTicks as tick}
							<line x1="0" y1={tick.y} x2={xBase} y2={tick.y} />
						{/each}
					</g>

					<!-- Paper citation lines (cumulative) -->
					{#each fb.figPapers as paper}
						<path
							role="region"
							fill="none"
							stroke={getColor(paper.rate)}
							stroke-width={paper.i === highlighted ? 0.18 : 0.1}
							stroke-linecap="round"
							stroke-linejoin="round"
							d={paper.path}
							opacity={paper.i === highlighted ? 1.0 : 0.4}
							id="hit-paper-path-{paper.i}"
							on:mouseover={() => fixHighlight(paper.i)}
							on:focus={() => fixHighlight(paper.i)}
						/>
					{/each}

					<!-- Highlighted paper name follows the line via textPath -->
					{#if highlightedVis !== undefined}
						{@const hp = fb.figPapers[highlightedVis]}
						<text font-size="0.4" style="fill: {getColor(hp.rate)}" dy="-0.28">
							<textPath href="#hit-paper-path-{hp.i}" startOffset="3%" text-anchor="start"
								>{hp.pathName}</textPath
							>
						</text>
					{/if}

					<!-- X axis baseline and ticks -->
					<g
						stroke-width="0.03"
						stroke="var(--color-text)"
						fill="var(--color-text)"
						font-size={fontSize}
					>
						<path d="M 0 0 h {xBase}" />
						{#each fb.yearTicks as tick}
							<path d="M {tick.x} 0 v 0.35" />
							{#if tick.name !== undefined}
								<text x={tick.x} y="0.9" text-anchor="middle">{tick.name}</text>
							{/if}
						{/each}
					</g>

					<!-- Paper publication year markers (only when x is calendar-aligned) -->
					{#if !fb.align}
						{#each fb.pubMarks as mark}
							<line
								x1={mark.x}
								y1="0"
								x2={mark.x}
								y2="0.45"
								stroke={mark.color}
								stroke-width="0.09"
							/>
							<text
								x={mark.x}
								y={mark.row === 0 ? 1.65 : 2.15}
								text-anchor="middle"
								font-size="0.38"
								style="fill: {mark.color}"
								stroke="none">{mark.year}</text
							>
						{/each}
					{/if}

					<!-- Y-axis ticks and labels -->
					<g fill="var(--color-text)" font-size="0.65">
						{#each fb.yTicks as tick}
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
			{/if}
		</div>
	{/if}

	<div class="sidebar">
		<HitPaperExplainer />

		<ol id="paper-list" bind:this={listContainer}>
			{#each chartPapers as paper, i}
				{@const source = resolveSourceName(paper.source, entityAtts)}
				{@const authors = shortAuthors(paper)}
				{@const expanded = expandedSet.has(i)}
				<li
					style={getLiStyle(i, visInds ?? [], highlighted)}
					data-index={i}
					on:mouseover={() => fixHighlight(i)}
					on:focus={() => fixHighlight(i)}
				>
					<div class="paper-header">
						<span class="paper-title">
							{#if paper.doi.length > 0}
								<a href="https://doi.org/{paper.doi}" target="_blank">{@html paper.name}</a>
							{:else}
								{@html paper.name}
							{/if}
						</span>
						<button
							class="expand-btn"
							on:click|stopPropagation={() => toggleExpand(i)}
							aria-label={expanded ? 'Collapse' : 'Expand'}>{expanded ? '▲' : '▼'}</button
						>
					</div>
					<div class="paper-meta">
						<span class="paper-year">{paper.year}</span>
						<span class="paper-cites">{formatNumber(paper.citations)} citations</span>
						{#if authors}<span class="paper-authors">{authors}</span>{/if}
						{#if source}<span class="paper-source">{source}</span>{/if}
						{#if paper.hitSemId}
							<a
								href="/hit-papers/{paper.hitSemId}"
								class="paper-profile-link"
								on:click|stopPropagation={() => {}}>profile →</a
							>
						{/if}
					</div>
					{#if expanded}
						<div class="paper-details">
							{#if paper.authorships.length > 2}
								<div class="detail-row">
									<span class="detail-label">Authors:</span>
									<span>{allAuthors(paper).join(', ')}</span>
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
							{#if paper.hitBm && paper.hitBm >= bmThreshold}
								<div class="detail-row">
									<span class="detail-label">Top-1% benchmark:</span>
									<span>{formatNumber(paper.hitBm)} citations</span>
								</div>
								<div class="detail-row selection-basis">
									<span class="detail-label">Performance:</span>
									<span>{overperf(paper).toFixed(1)}× above cohort benchmark</span>
								</div>
							{:else if paper.citations >= globalMinCites}
								<div class="detail-row selection-basis">
									<span class="detail-label">Selection:</span>
									<span>Universal threshold (≥{globalMinCites} citations)</span>
								</div>
							{/if}
						</div>
					{/if}
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
		transition: opacity 0.15s, background 0.15s;
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
	}

	text {
		pointer-events: none;
	}

	path {
		transition: opacity 400ms, stroke-width 400ms;
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
		margin-top: var(--unified-margin);
		padding: var(--unified-padding);
		font-weight: 600;
	}

	.paper-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 8px;
	}

	.paper-title {
		flex: 1;
		min-width: 0;
	}

	.expand-btn {
		background: none;
		border: none;
		cursor: pointer;
		font-size: var(--text-xs);
		opacity: 0.55;
		padding: 0 2px;
		flex-shrink: 0;
		line-height: 1.6;
	}

	.paper-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 4px 12px;
		font-size: var(--text-sm);
		font-weight: 400;
		opacity: 0.65;
		margin-top: 2px;
	}

	.paper-year {
		font-weight: 600;
	}

	.paper-cites {
		font-weight: 600;
	}

	.paper-source {
		font-style: italic;
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
