<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { COMPLETE_YEAR } from '$lib/constants';
	import type { Paper } from '$lib/tree-types';
	import type { WorksLoader } from '$lib/utils/works-loader';
	import { resolveSourceName, resolveLinkedAuthors, htmlToText } from '$lib/utils/paper-helpers';
	import { formatReference, type CitationStyle } from '$lib/utils/reference-format';
	import ExportControls from './ExportControls.svelte';

	export let works: WorksLoader;
	export let disownedWids: Set<number> = new Set();
	export let mergedPairs: [number, number][] = [];
	export let isOwner = false;

	type MergeEvent = { keep: number; drop: number };
	const dispatch = createEventDispatcher<{
		disown: number;
		undisown: number;
		merge: MergeEvent;
		unmerge: MergeEvent;
	}>();

	// Data layer lives in the shared works loader (also feeding the co-author network),
	// so every page is fetched once. These aliases keep the rest of the component unchanged.
	$: papers = $works.papers;
	$: entityAtts = $works.entityAtts;
	$: discAuthorNames = $works.discAuthorNames;
	$: totalPapers = $works.totalPapers;
	$: sliceEnd = $works.sliceEnd;
	$: loading = $works.loading;
	$: initialLoaded = $works.initialLoaded;
	$: ownerUnlocked = initialLoaded && totalPapers > 0 && sliceEnd >= totalPapers;

	let sortBy: 'year' | 'citations' = 'year';
	let sortDir: 'asc' | 'desc' = 'desc';
	let minCitations = 0;
	let minYear = COMPLETE_YEAR;
	let topN = 0;
	let citationStyle: CitationStyle = 'html';

	// Merge UI state — multi-select papers, pick the representative to keep, merge the rest into it.
	let selectedWids: Set<number> = new Set();
	let repWid: number | null = null;

	async function loadMore() {
		await works.loadMore();
	}

	// Sorting the full list, and owners (logged in) inspecting their works, both
	// require every page present — a partial sort would mislead. The page-count
	// reads live in plain functions, not in the `$:` deps, so loadAll mutating them
	// can't feed back into these statements (no reactive loop).
	let prevSortId: string | null = null;
	$: sortId = `${sortBy}|${sortDir}`;
	$: if (initialLoaded) onSortChange(sortId);
	$: if (initialLoaded && isOwner) ensureFullyLoaded();

	function onSortChange(id: string) {
		if (prevSortId !== null && id !== prevSortId) ensureFullyLoaded();
		prevSortId = id;
	}

	function ensureFullyLoaded() {
		if (sliceEnd < totalPapers) void works.loadAll();
	}

	$: mergedDrops = new Set(mergedPairs.map(([, d]) => d));
	$: mergedKeepCounts = mergedPairs.reduce(
		(acc, [k]) => acc.set(k, (acc.get(k) ?? 0) + 1),
		new Map<number, number>()
	);
	$: activePapers = papers.filter((p) => !disownedWids.has(p.wid) && !mergedDrops.has(p.wid));
	$: disownedPapersList = papers.filter((p) => disownedWids.has(p.wid));
	$: mergedDropPapers = papers.filter((p) => mergedDrops.has(p.wid));

	$: displayPapers = (() => {
		let result = activePapers.filter(
			(p) => p.citations >= minCitations && (minYear === 0 || p.year >= minYear)
		);
		if (topN > 0) {
			result = [...result].sort((a, b) => b.citations - a.citations).slice(0, topN);
		}
		return result.sort((a, b) => {
			const diff = sortBy === 'citations' ? a.citations - b.citations : a.year - b.year;
			return sortDir === 'desc' ? -diff : diff;
		});
	})();

	function setSort(col: 'year' | 'citations') {
		if (sortBy === col) sortDir = sortDir === 'desc' ? 'asc' : 'desc';
		else {
			sortBy = col;
			sortDir = 'desc';
		}
	}

	function pickDefaultRep(sel: Set<number>): number | null {
		// Default the kept paper to the most-cited in the selection — usually the canonical version.
		let best: number | null = null;
		let bestCites = -1;
		for (const wid of sel) {
			const p = papers.find((q) => q.wid === wid);
			if (p && p.citations > bestCites) {
				bestCites = p.citations;
				best = wid;
			}
		}
		return best;
	}

	function toggleSelect(wid: number) {
		const next = new Set(selectedWids);
		if (next.has(wid)) next.delete(wid);
		else next.add(wid);
		selectedWids = next;
		if (repWid === null || !next.has(repWid)) repWid = pickDefaultRep(next);
	}

	function clearSelection() {
		selectedWids = new Set();
		repWid = null;
	}

	function confirmMultiMerge() {
		// One merge event per non-representative paper; the parent appends each pair synchronously
		// before its await, so a batch of dispatches accumulates correctly.
		if (repWid === null || selectedWids.size < 2) return;
		for (const wid of selectedWids) {
			if (wid !== repWid) dispatch('merge', { keep: repWid, drop: wid });
		}
		clearSelection();
	}

	$: selectedPapers = [...selectedWids]
		.map((wid) => papers.find((p) => p.wid === wid))
		.filter((p): p is Paper => p != null);

	$: showOwnerActions = isOwner && ownerUnlocked && citationStyle === 'html';
	$: showChangesSections = isOwner ? ownerUnlocked : true;
	$: allLoaded = sliceEnd >= totalPapers && initialLoaded;
	$: loadMoreLabel = (() => {
		const count = `${sliceEnd} of ${totalPapers}`;
		if (isOwner && !ownerUnlocked) return `Load all to suggest changes (${count})`;
		return `Load more (${count})`;
	})();
</script>

<div class="all-works">
	{#if !initialLoaded}
		<p class="status">Loading papers...</p>
	{:else}
		<ExportControls
			filteredPapers={displayPapers}
			totalCount={activePapers.length}
			{entityAtts}
			{discAuthorNames}
			bind:sortBy
			bind:minCitations
			bind:minYear
			bind:topN
			bind:citationStyle
		/>

		{#if !allLoaded}
			<button class="load-more load-more-top" on:click={loadMore} disabled={loading}>
				{loading ? 'Loading...' : loadMoreLabel}
			</button>
		{/if}

		{#if citationStyle === 'html'}
			<div class="works-scroll">
				<table class="works-table">
					<thead>
						<tr>
							<th class="col-num">#</th>
							<th class="col-main">Work</th>
							<th class="col-year">
								<button
									class="sort-btn"
									class:sorted={sortBy === 'year'}
									on:click={() => setSort('year')}
								>
									Year{#if sortBy === 'year'}<span class="sort-ind"
											>{sortDir === 'desc' ? '▾' : '▴'}</span
										>{/if}
								</button>
							</th>
							<th class="col-cites">
								<button
									class="sort-btn"
									class:sorted={sortBy === 'citations'}
									on:click={() => setSort('citations')}
								>
									Indexed citations{#if sortBy === 'citations'}<span class="sort-ind"
											>{sortDir === 'desc' ? '▾' : '▴'}</span
										>{/if}
								</button>
							</th>
							{#if showOwnerActions}<th class="col-select">Merge</th><th
									class="col-actions"
									aria-label="Actions"
								></th>{/if}
						</tr>
					</thead>
					<tbody>
						{#each displayPapers as paper, idx (paper.wid)}
							{@const mergeCount = mergedKeepCounts.get(paper.wid) ?? 0}
							{@const isSelected = selectedWids.has(paper.wid)}
							{@const isRep = repWid === paper.wid && selectedWids.size >= 2}
							{@const authors = resolveLinkedAuthors(paper, entityAtts, discAuthorNames)}
							{@const journal = resolveSourceName(paper.source, entityAtts)}
							<tr class:selected-row={isSelected} class:rep-row={isRep}>
								<td class="col-num">{idx + 1}</td>
								<td class="col-main">
									<div class="paper-title">
										{#if paper.doi}<a
												href="https://doi.org/{paper.doi}"
												target="_blank"
												rel="noopener">{@html paper.name}</a
											>{:else}{@html paper.name}{/if}
									</div>
									<div class="paper-byline">
										{#if journal}<em class="byline-journal">{journal}</em>{/if}
										{#if authors.length}{#if journal}<span class="byline-sep">·</span
												>{/if}{#each authors as a, i (i)}{#if a.url}<a
														class="author-link"
														href={a.url}>{a.name}</a
													>{:else}<span class="author-plain">{a.name}</span
													>{/if}{#if i < authors.length - 1}<span class="comma"
														>,
													</span>{/if}{/each}{/if}
									</div>
									{#if paper.hitSemId}<a href="/hit-papers/{paper.hitSemId}" class="hit-breakdown"
											>Hit paper breakdown →</a
										>{/if}</td
								>
								<td class="col-year">{paper.year}</td>
								<td class="col-cites">
									{paper.citations}{#if mergeCount > 0}<span
											class="merge-badge"
											title="merged duplicates">+{mergeCount}</span
										>{/if}
								</td>
								{#if showOwnerActions}
									<td class="col-select">
										<input
											type="checkbox"
											checked={isSelected}
											on:change={() => toggleSelect(paper.wid)}
											aria-label="Select for merge"
										/>
										{#if isRep}<span class="rep-tag">keep</span>{/if}
									</td>
									<td class="col-actions">
										<button
											class="btn-sm destructive"
											on:click={() => dispatch('disown', paper.wid)}>Remove</button
										>
									</td>
								{/if}
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{:else}
			<div class="paper-list">
				{#each displayPapers as paper (paper.wid)}
					<div class="paper-row">
						<div class="paper-info">
							<span class="paper-ref"
								>{formatReference(paper, entityAtts, discAuthorNames, citationStyle)}</span
							>
						</div>
					</div>
				{/each}
			</div>
		{/if}

		{#if showOwnerActions && selectedWids.size > 0}
			<div class="merge-bar">
				<div class="merge-bar-main">
					<span class="merge-count">{selectedWids.size} selected</span>
					{#if selectedWids.size >= 2}
						<label class="merge-rep">
							Keep
							<select bind:value={repWid}>
								{#each selectedPapers as p (p.wid)}
									<option value={p.wid}>{htmlToText(p.name)} ({p.citations} cites)</option>
								{/each}
							</select>
						</label>
					{/if}
				</div>
				<div class="merge-bar-actions">
					{#if selectedWids.size >= 2}
						<button class="btn-sm confirm" on:click={confirmMultiMerge}
							>Merge {selectedWids.size - 1} into the kept paper</button
						>
					{:else}
						<span class="merge-hint">Select another paper to merge it in</span>
					{/if}
					<button class="btn-sm" on:click={clearSelection}>Clear</button>
				</div>
			</div>
		{/if}

		{#if mergedDropPapers.length > 0 && showChangesSections}
			<details class="merged-section">
				<summary>{isOwner ? 'Merged' : 'Merged by author'} ({mergedDropPapers.length})</summary>
				<div class="paper-list dimmed">
					{#each mergedDropPapers as paper (paper.wid)}
						{@const keepWid = mergedPairs.find(([, d]) => d === paper.wid)?.[0]}
						{@const keepPaper = papers.find((p) => p.wid === keepWid)}
						<div class="paper-row">
							<div class="paper-info">
								<span class="paper-ref">{@html paper.name}</span>
								<span class="paper-meta">
									{paper.year}
									{#if keepPaper}
										· merged into: {keepPaper.name}{/if}
								</span>
							</div>
							{#if isOwner && keepWid !== undefined}
								<button
									class="btn-sm"
									on:click={() => dispatch('unmerge', { keep: keepWid, drop: paper.wid })}
									>Unmerge</button
								>
							{/if}
						</div>
					{/each}
				</div>
			</details>
		{/if}

		{#if disownedPapersList.length > 0 && showChangesSections}
			<details class="disowned-section">
				<summary>{isOwner ? 'Removed' : 'Removed by author'} ({disownedPapersList.length})</summary>
				<div class="paper-list dimmed">
					{#each disownedPapersList as paper (paper.wid)}
						{@const source = resolveSourceName(paper.source, entityAtts)}
						<div class="paper-row">
							<div class="paper-info">
								<span class="paper-ref">{@html paper.name}</span>
								<span class="paper-meta"
									>{paper.year}{#if source}
										· {source}{/if}</span
								>
							</div>
							{#if isOwner}
								<button class="btn-sm" on:click={() => dispatch('undisown', paper.wid)}>Undo</button
								>
							{/if}
						</div>
					{/each}
				</div>
			</details>
		{/if}

		{#if !allLoaded}
			<button class="load-more" on:click={loadMore} disabled={loading}>
				{loading ? 'Loading...' : loadMoreLabel}
			</button>
		{/if}
	{/if}
</div>

<style>
	.all-works {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.paper-list {
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	/* On narrow screens the table's columns can't shrink below their content; scroll it horizontally
	   instead of letting it push the whole page wide. */
	.works-scroll {
		overflow-x: auto;
	}

	.works-table {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--text-base);
		line-height: 1.3;
	}

	.works-table thead th {
		text-align: left;
		font-weight: 600;
		font-size: var(--text-xs);
		text-transform: uppercase;
		letter-spacing: 0.03em;
		opacity: 0.55;
		padding: 4px 8px;
		border-bottom: 1px solid rgba(var(--color-range-15), 0.2);
	}

	.works-table tbody td {
		padding: 6px 8px;
		vertical-align: top;
		border-bottom: 1px solid rgba(var(--color-range-15), 0.06);
	}

	.works-table thead th.col-year,
	.works-table thead th.col-cites {
		text-align: right;
		opacity: 1; /* dim via the button so the sorted state can brighten past 0.55 */
	}

	.sort-btn {
		font: inherit;
		text-transform: inherit;
		letter-spacing: inherit;
		color: inherit;
		background: none;
		border: none;
		padding: 0;
		cursor: pointer;
		white-space: nowrap;
		opacity: 0.55;
	}

	.sort-btn:hover,
	.sort-btn.sorted {
		opacity: 1;
	}

	.sort-ind {
		margin-left: 3px;
	}

	.works-table tr.selected-row {
		background: rgba(var(--color-range-15), 0.08);
	}

	.works-table tr.rep-row {
		background: rgba(var(--color-range-15), 0.16);
	}

	.col-select {
		width: 1%;
		white-space: nowrap;
		text-align: center;
		font-size: var(--text-xs);
	}

	.col-select input {
		cursor: pointer;
	}

	.rep-tag {
		display: block;
		margin-top: 2px;
		font-size: var(--text-xs);
		text-transform: uppercase;
		letter-spacing: 0.04em;
		opacity: 0.7;
	}

	.col-num {
		text-align: right;
		opacity: 0.55;
		font-variant-numeric: tabular-nums;
		width: 2.5rem;
	}

	.col-main {
		width: auto;
		overflow-wrap: anywhere;
	}

	.paper-title {
		font-weight: 500;
	}

	.paper-title a {
		color: inherit;
		text-decoration: none;
	}

	.paper-title a:hover {
		text-decoration: underline;
	}

	.paper-byline {
		margin-top: 3px;
		font-size: var(--text-xs);
		line-height: 1.45;
		opacity: 0.7;
	}

	.byline-sep {
		margin: 0 5px;
		opacity: 0.45;
	}

	.byline-journal {
		font-style: italic;
	}

	.author-link {
		color: inherit;
		text-decoration: none;
		white-space: nowrap;
		border-bottom: 1px dotted rgba(var(--color-range-15), 0.45);
	}

	.author-link:hover {
		border-bottom-style: solid;
	}

	.author-plain {
		white-space: nowrap;
		opacity: 0.85;
	}

	.col-year {
		text-align: right;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
		width: 3rem;
	}

	.col-cites {
		text-align: right;
		font-variant-numeric: tabular-nums;
		white-space: nowrap;
		width: 5rem;
	}

	.col-actions {
		white-space: nowrap;
	}

	.paper-row {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 8px;
		padding: 6px 0;
		border-bottom: 1px solid rgba(var(--color-range-15), 0.06);
	}

	.paper-info {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}

	.paper-ref {
		font-size: var(--text-base);
		line-height: 1.3;
		overflow-wrap: anywhere;
	}

	.paper-ref :global(a) {
		color: inherit;
		text-decoration: none;
	}

	.paper-ref :global(a:hover) {
		text-decoration: underline;
	}

	.paper-ref :global(em) {
		font-style: italic;
	}

	.paper-meta {
		font-size: var(--text-xs);
		opacity: 0.5;
		margin-left: var(--text-md);
		display: flex;
		flex-wrap: wrap;
		gap: 6px;
		align-items: center;
		overflow-wrap: anywhere;
	}

	.hit-breakdown {
		display: inline-block;
		margin-top: 4px;
		font-size: var(--text-xs);
		font-weight: 600;
		color: var(--color-text);
		text-decoration: none;
		opacity: 0.65;
	}

	.hit-breakdown:hover {
		opacity: 1;
		text-decoration: underline;
	}

	.merge-badge {
		font-size: var(--text-xs);
		padding: 1px 5px;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		opacity: 1;
	}

	.merge-bar {
		position: sticky;
		bottom: 0;
		z-index: 5;
		display: flex;
		flex-wrap: wrap;
		gap: 10px 16px;
		align-items: center;
		justify-content: space-between;
		padding: 10px 14px;
		background: var(--text-bg-2);
		border: 1px solid var(--color-theme-darkblue);
		box-shadow: 0 -3px 12px var(--color-theme-shadow);
	}

	.merge-bar-main {
		display: flex;
		flex-wrap: wrap;
		gap: 8px 14px;
		align-items: center;
		min-width: 0;
	}

	.merge-count {
		font-weight: 700;
	}

	.merge-rep {
		display: flex;
		gap: 6px;
		align-items: center;
		font-size: var(--text-sm);
		min-width: 0;
	}

	.merge-rep select {
		max-width: 340px;
	}

	.merge-bar-actions {
		display: flex;
		gap: 8px;
		align-items: center;
	}

	.merge-hint {
		font-size: var(--text-sm);
		opacity: 0.7;
	}

	.load-more {
		align-self: center;
		padding: 6px 16px;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		background: none;
		cursor: pointer;
		font-size: var(--text-sm);
		color: var(--color-text);
		font-family: inherit;
	}

	.load-more:hover:not(:disabled) {
		background: rgba(var(--color-range-15), 0.05);
	}

	.load-more:disabled {
		opacity: 0.4;
		cursor: default;
	}

	.merged-section,
	.disowned-section {
		margin-top: 8px;
	}

	.merged-section summary,
	.disowned-section summary {
		cursor: pointer;
		font-size: var(--text-sm);
		opacity: 0.5;
	}

	.load-more-top {
		align-self: flex-start;
	}

	@media (max-width: 640px) {
		.works-table {
			font-size: var(--text-sm);
		}

		.works-table thead th,
		.works-table tbody td {
			padding: 7px 4px;
		}

		.col-num {
			width: 1.4rem;
			font-size: var(--text-xs);
		}

		.col-year {
			width: 2.4rem;
		}

		.col-cites {
			width: 3.4rem;
		}
	}

	@media (min-width: 1200px) {
		.paper-ref {
			font-size: var(--text-md);
		}

		.paper-meta {
			font-size: var(--text-base);
		}

		.works-table {
			font-size: var(--text-md);
		}

		.paper-byline {
			font-size: var(--text-base);
		}
	}
</style>
