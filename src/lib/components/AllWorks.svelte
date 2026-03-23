<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import { BE_REMOTE_URL, COMPLETE_YEAR } from '$lib/constants';
	import type { Paper, EntityAttsForLinks, PaginatedPaperSetResp } from '$lib/tree-types';
	import { resolveSourceName } from '$lib/utils/paper-helpers';
	import { formatReference, type CitationStyle } from '$lib/utils/reference-format';
	import ExportControls from './ExportControls.svelte';

	export let semanticId: string;
	export let entityAtts: EntityAttsForLinks;
	export let discAuthorNames: Record<string, string>;
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

	let papers: Paper[] = [];
	let totalPapers = 0;
	let sliceEnd = 0;
	let loading = false;
	let initialLoaded = false;

	let sortBy: 'year' | 'citations' = 'year';
	let minCitations = 0;
	let minYear = COMPLETE_YEAR;
	let topN = 0;
	let citationStyle: CitationStyle = 'html';

	// Merge UI state
	let mergingWid: number | null = null;
	let mergeConfirm: { keep: number; drop: number } | null = null;

	async function fetchPage(from: number) {
		loading = true;
		try {
			const resp = await fetch(`${BE_REMOTE_URL}/works/authors/${semanticId}/${from}`);
			const data: PaginatedPaperSetResp = await resp.json();
			papers = [...papers, ...data.resp.papers];
			totalPapers = data.totalPapers;
			sliceEnd = data.sliceStart + data.resp.papers.length;
			for (const [k, v] of Object.entries(data.resp.entityAtts)) {
				entityAtts[k] = { ...(entityAtts[k] ?? {}), ...v };
			}
			entityAtts = entityAtts;
			discAuthorNames = { ...discAuthorNames, ...data.resp.discAuthorNames };
		} finally {
			loading = false;
		}
	}

	onMount(async () => {
		await fetchPage(0);
		initialLoaded = true;
	});

	function loadMore() {
		if (!loading && sliceEnd < totalPapers) fetchPage(sliceEnd);
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
		return result.sort((a, b) =>
			sortBy === 'citations' ? b.citations - a.citations : b.year - a.year
		);
	})();

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
		// Default: higher citations paper is kept
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

	$: showOwnerActions = isOwner && citationStyle === 'html';
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

		{#if mergingWid !== null}
			{@const sourcePaper = papers.find((p) => p.wid === mergingWid)}
			<div class="merge-mode-bar">
				<span
					>Merging: <em>{sourcePaper?.name ?? mergingWid}</em> — click another paper to select target</span
				>
				<button class="cancel-btn" on:click={cancelMerge}>Cancel</button>
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
					<button class="swap-btn" on:click={swapMergeKeepDrop} title="Swap keep/drop">⇄</button>
					<div class="merge-paper">
						<span class="merge-label dropped">Drop</span>
						<span class="merge-title">{mergeConfirmPapers.drop.name}</span>
						<span class="merge-meta"
							>{mergeConfirmPapers.drop.citations} cites · {mergeConfirmPapers.drop.year}</span
						>
					</div>
				</div>
				<p class="merge-note">
					The dropped paper will be hidden from your list. This change is local only — contact us to
					apply it to all figures.
				</p>
				<div class="merge-confirm-actions">
					<button class="confirm-btn" on:click={confirmMerge}>Confirm merge</button>
					<button class="cancel-btn" on:click={cancelMerge}>Cancel</button>
				</div>
			</div>
		{/if}

		<div class="paper-list">
			{#each displayPapers as paper (paper.wid)}
				{@const mergeCount = mergedKeepCounts.get(paper.wid) ?? 0}
				{@const isMergingSource = mergingWid === paper.wid}
				<div class="paper-row" class:merging-source={isMergingSource}>
					<div class="paper-info">
						{#if citationStyle === 'html'}
							<span class="paper-ref"
								>{@html formatReference(paper, entityAtts, discAuthorNames, 'html')}</span
							>
							<span class="paper-meta">
								{#if paper.citations > 0}{paper.citations} indexed citations{/if}
								{#if mergeCount > 0}<span class="merge-badge">+{mergeCount} merged</span>{/if}
							</span>
						{:else}
							<span class="paper-ref"
								>{formatReference(paper, entityAtts, discAuthorNames, citationStyle)}</span
							>
						{/if}
					</div>
					{#if showOwnerActions}
						{#if isMergingSource}
							<button class="cancel-btn" on:click={cancelMerge}>Cancel</button>
						{:else if mergingWid !== null}
							<button class="merge-here-btn" on:click={() => selectMergeTarget(paper)}
								>Merge here</button
							>
						{:else}
							<div class="paper-actions">
								<button class="action-btn" on:click={() => startMerge(paper.wid)}>Merge</button>
								<button class="action-btn disown" on:click={() => dispatch('disown', paper.wid)}
									>Disown</button
								>
							</div>
						{/if}
					{/if}
				</div>
			{/each}
		</div>

		{#if mergedDropPapers.length > 0 && isOwner}
			<details class="merged-section">
				<summary>Merged ({mergedDropPapers.length})</summary>
				<div class="paper-list dimmed">
					{#each mergedDropPapers as paper (paper.wid)}
						{@const keepWid = mergedPairs.find(([, d]) => d === paper.wid)?.[0]}
						{@const keepPaper = papers.find((p) => p.wid === keepWid)}
						<div class="paper-row">
							<div class="paper-info">
								<span class="paper-ref">{@html paper.name}</span>
								<span class="paper-meta">
									{paper.year}
									{#if keepPaper} · merged into: {keepPaper.name}{/if}
								</span>
							</div>
							{#if keepWid !== undefined}
								<button
									class="action-btn"
									on:click={() => dispatch('unmerge', { keep: keepWid, drop: paper.wid })}
									>Unmerge</button
								>
							{/if}
						</div>
					{/each}
				</div>
			</details>
		{/if}

		{#if disownedPapersList.length > 0 && isOwner}
			<details class="disowned-section">
				<summary>Disowned ({disownedPapersList.length})</summary>
				<div class="paper-list dimmed">
					{#each disownedPapersList as paper (paper.wid)}
						{@const source = resolveSourceName(paper.source, entityAtts)}
						<div class="paper-row">
							<div class="paper-info">
								<span class="paper-ref">{@html paper.name}</span>
								<span class="paper-meta"
									>{paper.year}{#if source} · {source}{/if}</span
								>
							</div>
							<button class="action-btn" on:click={() => dispatch('undisown', paper.wid)}
								>Undo</button
							>
						</div>
					{/each}
				</div>
			</details>
		{/if}

		{#if sliceEnd < totalPapers}
			<button class="load-more" on:click={loadMore} disabled={loading}>
				{loading ? 'Loading...' : `Load more (${sliceEnd} of ${totalPapers})`}
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

	.paper-row {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 8px;
		padding: 6px 0;
		border-bottom: 1px solid rgba(var(--color-range-15), 0.06);
	}

	.paper-row.merging-source {
		background: rgba(var(--color-range-15), 0.04);
		border-radius: 3px;
		padding-left: 6px;
	}

	.paper-info {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}

	.paper-ref {
		font-size: 0.85rem;
		line-height: 1.3;
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
		font-size: 0.7rem;
		opacity: 0.5;
		display: flex;
		gap: 6px;
		align-items: center;
	}

	.merge-badge {
		font-size: 0.6rem;
		padding: 1px 5px;
		border-radius: 3px;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		opacity: 1;
	}

	.paper-actions {
		display: flex;
		gap: 4px;
		flex-shrink: 0;
	}

	.action-btn {
		flex-shrink: 0;
		font-size: 0.65rem;
		padding: 2px 8px;
		border-radius: 3px;
		border: 1px solid rgba(var(--color-range-15), 0.15);
		background: none;
		cursor: pointer;
		color: var(--color-text);
		opacity: 0.5;
	}

	.action-btn:hover {
		opacity: 1;
	}

	.action-btn.disown {
		opacity: 0.35;
	}

	.merge-here-btn {
		flex-shrink: 0;
		font-size: 0.65rem;
		padding: 2px 8px;
		border-radius: 3px;
		border: 1px solid rgba(var(--color-range-15), 0.3);
		background: rgba(var(--color-range-15), 0.05);
		cursor: pointer;
		color: var(--color-text);
	}

	.merge-here-btn:hover {
		background: rgba(var(--color-range-15), 0.12);
	}

	.cancel-btn {
		flex-shrink: 0;
		font-size: 0.65rem;
		padding: 2px 8px;
		border-radius: 3px;
		border: 1px solid rgba(var(--color-range-15), 0.15);
		background: none;
		cursor: pointer;
		color: var(--color-text);
		opacity: 0.6;
	}

	.cancel-btn:hover {
		opacity: 1;
	}

	.merge-mode-bar {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
		padding: 8px 10px;
		border-radius: 4px;
		border: 1px dashed rgba(var(--color-range-15), 0.25);
		font-size: 0.75rem;
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
		border-radius: 4px;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		font-size: 0.75rem;
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
		font-size: 0.6rem;
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
		font-size: 0.75rem;
		line-height: 1.2;
	}

	.merge-meta {
		font-size: 0.65rem;
		opacity: 0.5;
	}

	.swap-btn {
		flex-shrink: 0;
		background: none;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		border-radius: 3px;
		cursor: pointer;
		font-size: 1rem;
		padding: 2px 6px;
		color: var(--color-text);
		opacity: 0.6;
	}

	.swap-btn:hover {
		opacity: 1;
	}

	.merge-note {
		font-size: 0.65rem;
		opacity: 0.45;
		margin: 0;
		font-style: italic;
	}

	.merge-confirm-actions {
		display: flex;
		gap: 8px;
	}

	.confirm-btn {
		font-size: 0.7rem;
		padding: 3px 12px;
		border-radius: 3px;
		border: 1px solid rgba(var(--color-range-15), 0.25);
		background: none;
		cursor: pointer;
		color: var(--color-text);
	}

	.confirm-btn:hover {
		background: rgba(var(--color-range-15), 0.08);
	}

	.load-more {
		align-self: center;
		padding: 6px 16px;
		border-radius: 4px;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		background: none;
		cursor: pointer;
		font-size: 0.8rem;
		color: var(--color-text);
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
		font-size: 0.8rem;
		opacity: 0.5;
	}

	.dimmed {
		opacity: 0.5;
	}

	.status {
		opacity: 0.6;
		font-style: italic;
	}

	@media (min-width: 1200px) {
		.paper-ref {
			font-size: 1rem;
		}

		.paper-meta {
			font-size: 0.85rem;
		}
	}
</style>
