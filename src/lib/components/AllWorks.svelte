<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { COMPLETE_YEAR } from '$lib/constants';
	import type { Paper } from '$lib/tree-types';
	import type { WorksLoader } from '$lib/utils/works-loader';
	import { resolveSourceName, resolveLinkedAuthors } from '$lib/utils/paper-helpers';
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

	// Merge UI state
	let mergingWid: number | null = null;
	let mergeConfirm: { keep: number; drop: number } | null = null;

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

	function startMerge(wid: number) {
		mergingWid = wid;
		mergeConfirm = null;
	}

	function cancelMerge() {
		mergingWid = null;
		mergeConfirm = null;
	}

	function selectMergeTarget(target: Paper) {
		if (mergingWid === null) return;
		const source = papers.find((p) => p.wid === mergingWid)!;
		const keep = source.citations >= target.citations ? source.wid : target.wid;
		const drop = keep === source.wid ? target.wid : source.wid;
		mergeConfirm = { keep, drop };
		mergingWid = null;
	}

	function swapMergeKeepDrop() {
		if (!mergeConfirm) return;
		mergeConfirm = { keep: mergeConfirm.drop, drop: mergeConfirm.keep };
	}

	function confirmMerge() {
		if (!mergeConfirm) return;
		dispatch('merge', mergeConfirm);
		mergeConfirm = null;
	}

	$: mergeConfirmPapers = mergeConfirm
		? {
				keep: papers.find((p) => p.wid === mergeConfirm!.keep),
				drop: papers.find((p) => p.wid === mergeConfirm!.drop)
			}
		: null;

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

		{#if mergingWid !== null}
			{@const sourcePaper = papers.find((p) => p.wid === mergingWid)}
			<div class="merge-mode-bar">
				<span
					>Merging: <em>{sourcePaper?.name ?? mergingWid}</em> — click another paper to select target</span
				>
				<button class="btn-sm" on:click={cancelMerge}>Cancel</button>
			</div>
		{/if}

		{#if mergeConfirm && mergeConfirmPapers?.keep && mergeConfirmPapers?.drop}
			<div class="merge-confirm-bar">
				<div class="merge-confirm-papers">
					<div class="merge-paper">
						<span class="merge-label kept">Keep</span>
						<span class="merge-title">{mergeConfirmPapers.keep.name}</span>
						<span class="merge-meta"
							>{mergeConfirmPapers.keep.citations} cites · {mergeConfirmPapers.keep.year}</span
						>
					</div>
					<button class="btn-sm icon" on:click={swapMergeKeepDrop} title="Swap keep/drop">⇄</button>
					<div class="merge-paper">
						<span class="merge-label dropped">Drop</span>
						<span class="merge-title">{mergeConfirmPapers.drop.name}</span>
						<span class="merge-meta"
							>{mergeConfirmPapers.drop.citations} cites · {mergeConfirmPapers.drop.year}</span
						>
					</div>
				</div>
				<p class="hint-text">
					The dropped paper will be hidden from your list. This change is local only — contact us to
					apply it to all figures.
				</p>
				<div class="merge-confirm-actions">
					<button class="btn-sm confirm" on:click={confirmMerge}>Confirm merge</button>
					<button class="btn-sm" on:click={cancelMerge}>Cancel</button>
				</div>
			</div>
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
							{#if showOwnerActions}<th class="col-actions" aria-label="Actions"></th>{/if}
						</tr>
					</thead>
					<tbody>
						{#each displayPapers as paper, idx (paper.wid)}
							{@const mergeCount = mergedKeepCounts.get(paper.wid) ?? 0}
							{@const isMergingSource = mergingWid === paper.wid}
							{@const authors = resolveLinkedAuthors(paper, entityAtts, discAuthorNames)}
							{@const journal = resolveSourceName(paper.source, entityAtts)}
							<tr class:merging-source={isMergingSource}>
								<td class="col-num">{idx + 1}</td>
								<td class="col-main">
									<div class="paper-title">
										{#if paper.doi}<a
												href="https://doi.org/{paper.doi}"
												target="_blank"
												rel="noopener">{@html paper.name}</a
											>{:else}{@html paper.name}{/if}{#if paper.hitSemId}
											<a href="/hit-papers/{paper.hitSemId}" class="hit-page-link">breakdown →</a
											>{/if}
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
								</td>
								<td class="col-year">{paper.year}</td>
								<td class="col-cites">
									{paper.citations}{#if mergeCount > 0}<span
											class="merge-badge"
											title="merged duplicates">+{mergeCount}</span
										>{/if}
								</td>
								{#if showOwnerActions}
									<td class="col-actions">
										{#if isMergingSource}
											<button class="btn-sm" on:click={cancelMerge}>Cancel</button>
										{:else if mergingWid !== null}
											<button class="btn-sm active-bg" on:click={() => selectMergeTarget(paper)}
												>Merge here</button
											>
										{:else}
											<div class="paper-actions">
												<button class="btn-sm" on:click={() => startMerge(paper.wid)}>Merge</button>
												<button
													class="btn-sm destructive"
													on:click={() => dispatch('disown', paper.wid)}>Remove</button
												>
											</div>
										{/if}
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

	.works-table tr.merging-source {
		background: rgba(var(--color-range-15), 0.04);
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

	.hit-page-link {
		color: var(--color-text);
		text-decoration: none;
	}

	.hit-page-link:hover {
		opacity: 0.8;
	}

	.merge-badge {
		font-size: var(--text-xs);
		padding: 1px 5px;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		opacity: 1;
	}

	.paper-actions {
		display: flex;
		gap: 4px;
		flex-shrink: 0;
	}

	.merge-mode-bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
		padding: 8px 10px;
		border: 1px dashed rgba(var(--color-range-15), 0.25);
		font-size: var(--text-sm);
	}

	.merge-mode-bar em {
		font-style: italic;
		opacity: 0.7;
	}

	.merge-confirm-bar {
		display: flex;
		flex-direction: column;
		gap: 8px;
		padding: 10px 12px;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		font-size: var(--text-sm);
	}

	.merge-confirm-papers {
		display: flex;
		gap: 10px;
		align-items: center;
	}

	.merge-paper {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 2px;
	}

	.merge-label {
		font-size: var(--text-xs);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		opacity: 0.6;
	}

	.merge-label.kept {
		color: var(--color-theme-darkblue, inherit);
	}

	.merge-label.dropped {
		opacity: 0.4;
	}

	.merge-title {
		font-size: var(--text-sm);
		line-height: 1.2;
	}

	.merge-meta {
		font-size: var(--text-xs);
		opacity: 0.5;
	}

	.merge-confirm-actions {
		display: flex;
		gap: 8px;
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

		.paper-actions {
			flex-direction: column;
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
