<script lang="ts">
	import type { WorksLoader } from '$lib/utils/works-loader';
	import type { YearGroup, SortMode } from '$lib/utils/author-timeline';
	import { buildCoauthors, sortCoauthors, yearDomain, makeTicks } from '$lib/utils/author-timeline';

	export let works: WorksLoader;
	export let heroSemanticId: string = '';
	export let rootName: string = 'Person';

	type Tip = { x: number; y: number; flip: boolean; group: YearGroup } | null;

	const TIP_MAX = 6;

	let minPapers = 2;
	let sortMode: SortMode = 'first';
	let trackWidth = 0;
	let tip: Tip = null;

	// Hold the chart back until every page is in: rebuilding on each 200-paper append makes rows
	// appear and reorder mid-load, which reads as flashing. Compute only once fully loaded.
	$: loaded = $works.allLoaded;
	$: loadPct = $works.totalPapers ? Math.round(($works.sliceEnd / $works.totalPapers) * 100) : 0;
	$: coauthors = loaded
		? buildCoauthors($works.papers, $works.entityAtts, $works.discAuthorNames, heroSemanticId)
		: [];
	$: maxCount = coauthors.reduce((m, c) => Math.max(m, c.count), 1);
	$: rows = sortCoauthors(
		coauthors.filter((c) => c.count >= minPapers),
		sortMode
	);

	$: domain = yearDomain($works.papers);
	// Closes over reactive `domain`, so it must stay a `$:`-reassigned function (legacy mode).
	$: pctOf = (year: number) => ((year - domain.lo) / domain.span) * 100;
	$: ticks = makeTicks(domain, Math.max(2, Math.min(10, Math.floor((trackWidth || 600) / 64))));

	function tipFor(e: MouseEvent, group: YearGroup) {
		tip = { x: e.clientX, y: e.clientY, flip: e.clientX > window.innerWidth * 0.6, group };
	}
	function tipMove(e: MouseEvent) {
		if (tip) tip = { ...tip, x: e.clientX, y: e.clientY };
	}
	function tipFocus(e: FocusEvent & { currentTarget: HTMLButtonElement }, group: YearGroup) {
		const r = e.currentTarget.getBoundingClientRect();
		const x = r.left + r.width / 2;
		tip = { x, y: r.top, flip: x > window.innerWidth * 0.6, group };
	}
	function tipHide() {
		tip = null;
	}
</script>

<div class="tl">
	{#if !loaded}
		<div class="tl-loading">
			<div class="tl-spinner"></div>
			<p class="tl-loading-text">Loading every collaboration in {rootName}'s works…</p>
			<div class="tl-progress"><div class="tl-progress-bar" style="width:{loadPct}%"></div></div>
			<p class="tl-loading-sub">{$works.sliceEnd} of {$works.totalPapers || '…'} works</p>
		</div>
	{:else if coauthors.length === 0}
		<p class="tl-status">No co-authors found in these works.</p>
	{:else}
		<div class="tl-controls">
			<label class="tl-ctl">
				<span>Min. shared papers: <strong>{minPapers}</strong></span>
				<input type="range" min="1" max={Math.max(2, maxCount)} step="1" bind:value={minPapers} />
			</label>
			<label class="tl-ctl tl-sort">
				<span>Sort</span>
				<select bind:value={sortMode}>
					<option value="first">First collaboration</option>
					<option value="recent">Most recent</option>
					<option value="count">Most shared</option>
				</select>
			</label>
			<span class="tl-count">{rows.length} co-author{rows.length === 1 ? '' : 's'}</span>
		</div>

		{#if rows.length === 0}
			<p class="tl-status">
				No co-author shares at least {minPapers} papers — lower the threshold.
			</p>
		{:else}
			<div class="tl-chart">
				<div class="tl-scroll">
					<div class="tl-axis tl-grid">
						<div></div>
						<div class="tl-axis-track" bind:clientWidth={trackWidth}>
							{#each ticks as t (t)}
								<span class="tl-tick" style="left:{pctOf(t)}%">{t}</span>
							{/each}
						</div>
					</div>
					<div class="tl-body">
						<div class="tl-gridlines" aria-hidden="true">
							{#each ticks as t (t)}
								<span class="tl-grid-line" style="left:{pctOf(t)}%"></span>
							{/each}
						</div>

						{#each rows as row (row.key)}
							<div class="tl-row tl-grid">
								<div class="tl-name" title="{row.name} · {row.count} shared papers">
									{#if row.url}<a href={row.url}>{row.name}</a>{:else}{row.name}{/if}
								</div>
								<div class="tl-track">
									<div
										class="tl-bar"
										style="left:{pctOf(row.firstYear)}%; width:{pctOf(row.lastYear) -
											pctOf(row.firstYear)}%"
									></div>
									{#each row.groups as g (g.year)}
										<button
											class="tl-mark"
											class:hit={g.hasHit}
											style="left:{pctOf(g.year)}%; --n:{g.papers.length}"
											aria-label="{g.papers.length} paper{g.papers.length === 1
												? ''
												: 's'} in {g.year}{g.hasHit ? ', includes a hit paper' : ''}"
											on:mouseenter={(e) => tipFor(e, g)}
											on:mousemove={tipMove}
											on:mouseleave={tipHide}
											on:focus={(e) => tipFocus(e, g)}
											on:blur={tipHide}
										></button>
									{/each}
								</div>
							</div>
						{/each}
					</div>
				</div>
			</div>

			<div class="tl-legend">
				<span class="tl-lg"><span class="tl-sw tl-sw-mark"></span>Shared papers</span>
				<span class="tl-lg"><span class="tl-sw tl-sw-hit"></span>Includes a hit paper</span>
				<span class="tl-lg"><span class="tl-sw tl-sw-bar"></span>Collaboration span</span>
			</div>
		{/if}
	{/if}
</div>

{#if tip}
	<div class="tl-tip" class:flip={tip.flip} style="left:{tip.x}px; top:{tip.y}px">
		<div class="tl-tip-year">{tip.group.year}</div>
		<ul>
			{#each tip.group.papers.slice(0, TIP_MAX) as p (p.wid)}
				<li class:hit={p.isHit}>
					<span class="tl-tip-title">{@html p.name}</span>
					<span class="tl-tip-meta"
						>{p.citations.toLocaleString()} cites{#if p.isHit}
							· ★ hit{/if}</span
					>
				</li>
			{/each}
		</ul>
		{#if tip.group.papers.length > TIP_MAX}
			<div class="tl-tip-more">+{tip.group.papers.length - TIP_MAX} more</div>
		{/if}
	</div>
{/if}

<style>
	.tl {
		--accent: var(--color-theme-blue, #3b82f6);
		--tl-mark: rgb(var(--color-range-35));
		--tl-bar: rgba(var(--color-range-40), 0.45);
		--hair: rgba(var(--color-range-15), 0.12);
		--name-w: clamp(64px, 24%, 168px);
		display: flex;
		flex-direction: column;
		gap: 14px;
		width: 100%;
	}

	@media (prefers-color-scheme: dark) {
		.tl {
			--tl-mark: rgb(var(--color-range-80));
			--tl-bar: rgba(var(--color-range-90), 0.3);
		}
	}

	.tl-controls {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 10px 22px;
	}

	.tl-ctl {
		display: flex;
		align-items: center;
		gap: 8px;
		font-size: var(--text-xs);
		opacity: 0.85;
	}

	.tl-ctl input[type='range'] {
		width: clamp(90px, 28vw, 160px);
	}

	.tl-sort select {
		font: inherit;
		font-size: var(--control-bar-font);
		padding: var(--control-bar-pill-pad);
		border-radius: var(--control-bar-pill-radius);
		border: 1px solid rgba(var(--color-range-15), 0.2);
		background: none;
		color: inherit;
		cursor: pointer;
	}

	.tl-count {
		margin-left: auto;
		font-variant-numeric: tabular-nums;
		font-size: var(--text-xs);
		opacity: 0.6;
	}

	.tl-grid {
		display: grid;
		grid-template-columns: var(--name-w) 1fr;
		align-items: center;
		column-gap: 10px;
	}

	.tl-axis {
		position: sticky;
		top: 0;
		z-index: 1;
		padding-bottom: 2px;
		background: var(--text-bg, #fff);
		border-bottom: 1px solid var(--hair);
	}

	.tl-axis-track {
		position: relative;
		height: 16px;
	}

	.tl-tick {
		position: absolute;
		bottom: 0;
		transform: translateX(-50%);
		font-size: var(--text-xs);
		font-variant-numeric: tabular-nums;
		opacity: 0.5;
		white-space: nowrap;
	}

	.tl-scroll {
		max-height: min(56svh, 520px);
		overflow-y: auto;
		/* Marks/labels at the domain extremes overhang by a few px; without this, `overflow-y: auto`
		   silently promotes `overflow-x` to `auto` too and a stray horizontal scrollbar appears. The
		   inline padding keeps that overhang visible rather than clipped. */
		overflow-x: hidden;
		padding-inline: 10px;
	}

	.tl-body {
		position: relative;
	}

	.tl-gridlines {
		position: absolute;
		left: var(--name-w);
		right: 0;
		top: 0;
		bottom: 0;
		margin-left: 10px;
		pointer-events: none;
	}

	.tl-grid-line {
		position: absolute;
		top: 0;
		bottom: 0;
		width: 1px;
		transform: translateX(-50%);
		background: var(--hair);
	}

	.tl-row {
		min-height: 26px;
		border-bottom: 1px solid var(--hair);
	}

	.tl-name {
		font-size: var(--text-xs);
		line-height: 1.2;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		text-align: right;
		opacity: 0.85;
	}

	.tl-name a {
		color: inherit;
		text-decoration: none;
	}

	.tl-name a:hover {
		color: var(--accent);
		text-decoration: underline;
	}

	.tl-track {
		position: relative;
		height: 100%;
		min-height: 22px;
	}

	.tl-bar {
		position: absolute;
		top: 50%;
		height: 3px;
		min-width: 2px;
		transform: translateY(-50%);
		border-radius: 2px;
		background: var(--tl-bar);
		pointer-events: none;
	}

	.tl-mark {
		position: absolute;
		top: 50%;
		padding: 0;
		width: min(15px, calc(7px + (var(--n) - 1) * 3px));
		height: min(15px, calc(7px + (var(--n) - 1) * 3px));
		transform: translate(-50%, -50%);
		border: none;
		border-radius: 50%;
		background: var(--tl-mark);
		cursor: pointer;
		transition:
			transform 0.1s ease,
			box-shadow 0.1s ease;
	}

	.tl-mark.hit {
		background: var(--accent);
		box-shadow: 0 0 0 2px rgba(var(--color-range-40), 0.25);
	}

	.tl-mark:hover,
	.tl-mark:focus-visible {
		outline: none;
		transform: translate(-50%, -50%) scale(1.4);
		box-shadow: 0 0 0 3px rgba(var(--color-range-40), 0.3);
	}

	.tl-legend {
		display: flex;
		flex-wrap: wrap;
		gap: 6px 20px;
		font-size: var(--text-xs);
		opacity: 0.85;
	}

	.tl-lg {
		display: inline-flex;
		align-items: center;
		gap: 7px;
	}

	.tl-sw {
		flex-shrink: 0;
		display: inline-block;
	}

	.tl-sw-mark,
	.tl-sw-hit {
		width: 11px;
		height: 11px;
		border-radius: 50%;
		background: var(--tl-mark);
	}

	.tl-sw-hit {
		background: var(--accent);
	}

	.tl-sw-bar {
		width: 20px;
		height: 3px;
		border-radius: 2px;
		background: var(--tl-bar);
	}

	.tl-loading {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 12px;
		padding: 44px 16px;
		text-align: center;
	}

	.tl-spinner {
		width: 28px;
		height: 28px;
		border: 3px solid rgba(var(--color-range-40), 0.22);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: tl-spin 0.8s linear infinite;
	}

	@keyframes tl-spin {
		to {
			transform: rotate(360deg);
		}
	}

	.tl-loading-text {
		margin: 0;
		font-size: var(--text-sm);
		opacity: 0.75;
	}

	.tl-progress {
		width: min(320px, 80%);
		height: 4px;
		border-radius: 2px;
		background: rgba(var(--color-range-40), 0.18);
		overflow: hidden;
	}

	.tl-progress-bar {
		height: 100%;
		border-radius: 2px;
		background: var(--accent);
		transition: width 0.3s ease;
	}

	.tl-loading-sub {
		margin: 0;
		font-size: var(--text-xs);
		font-variant-numeric: tabular-nums;
		opacity: 0.55;
	}

	.tl-status {
		margin: 0;
		padding: 16px;
		text-align: center;
		font-size: var(--text-sm);
		opacity: 0.6;
	}

	.tl-tip {
		position: fixed;
		z-index: 30;
		max-width: min(320px, 80vw);
		padding: 8px 10px;
		transform: translate(12px, 12px);
		background: var(--text-bg, #fff);
		border: 1px solid var(--hair);
		border-radius: 8px;
		box-shadow: 0 8px 28px rgba(0, 0, 0, 0.18);
		pointer-events: none;
		font-size: var(--text-xs);
	}

	.tl-tip.flip {
		transform: translate(calc(-100% - 12px), 12px);
	}

	.tl-tip-year {
		font-variant-numeric: tabular-nums;
		font-weight: 600;
		opacity: 0.6;
		margin-bottom: 4px;
	}

	.tl-tip ul {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.tl-tip li.hit .tl-tip-title {
		font-weight: 600;
	}

	.tl-tip-title {
		display: block;
		line-height: 1.3;
		overflow-wrap: anywhere;
	}

	.tl-tip-meta {
		display: block;
		margin-top: 1px;
		opacity: 0.6;
		white-space: nowrap;
	}

	.tl-tip-more {
		margin-top: 6px;
		opacity: 0.5;
	}
</style>
