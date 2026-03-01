<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import { BE_REMOTE_URL } from '$lib/constants';
	import type { Paper, EntityAttsForLinks, PaginatedPaperSetResp } from '$lib/tree-types';
	import { resolveSourceName } from '$lib/utils/paper-helpers';
	import ExportControls from './ExportControls.svelte';

	export let semanticId: string;
	export let entityAtts: EntityAttsForLinks;
	export let discAuthorNames: Record<string, string>;
	export let disownedWids: Set<number> = new Set();
	export let isOwner = false;

	const dispatch = createEventDispatcher<{ disown: number; undisown: number }>();

	let papers: Paper[] = [];
	let totalPapers = 0;
	let sliceEnd = 0;
	let loading = false;
	let initialLoaded = false;

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

	$: activePapers = papers.filter(p => !disownedWids.has(p.wid));
	$: disownedPapersList = papers.filter(p => disownedWids.has(p.wid));
</script>

<div class="all-works">
	{#if !initialLoaded}
		<p class="status">Loading papers...</p>
	{:else}
		<ExportControls papers={activePapers} {entityAtts} {discAuthorNames} />

		<div class="paper-list">
			{#each activePapers as paper (paper.wid)}
				{@const source = resolveSourceName(paper.source, entityAtts)}
				<div class="paper-row">
					<div class="paper-info">
						<span class="paper-title">
							{#if paper.doi}
								<a href="https://doi.org/{paper.doi}" target="_blank" rel="noopener">{@html paper.name}</a>
							{:else}
								{@html paper.name}
							{/if}
						</span>
						<span class="paper-meta">
							{paper.year}
							{#if paper.citations > 0} · {paper.citations} citations{/if}
							{#if source} · {source}{/if}
						</span>
					</div>
					{#if isOwner}
						<button class="disown-btn" on:click={() => dispatch('disown', paper.wid)}>Disown</button>

					{/if}
				</div>
			{/each}
		</div>

		{#if disownedPapersList.length > 0 && isOwner}
			<details class="disowned-section">
				<summary>Disowned ({disownedPapersList.length})</summary>
				<div class="paper-list dimmed">
					{#each disownedPapersList as paper (paper.wid)}
						{@const source = resolveSourceName(paper.source, entityAtts)}
						<div class="paper-row">
							<div class="paper-info">
								<span class="paper-title">{@html paper.name}</span>
								<span class="paper-meta">{paper.year}{#if source} · {source}{/if}</span>
							</div>
							<button class="undo-btn" on:click={() => dispatch('undisown', paper.wid)}>Undo</button>

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

	.paper-info {
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}

	.paper-title {
		font-size: 0.85rem;
		font-weight: 500;
		line-height: 1.3;
	}

	.paper-title a {
		color: inherit;
		text-decoration: none;
	}

	.paper-title a:hover {
		text-decoration: underline;
	}

	.paper-meta {
		font-size: 0.7rem;
		opacity: 0.5;
	}

	.disown-btn, .undo-btn {
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

	.disown-btn:hover, .undo-btn:hover {
		opacity: 1;
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

	.disowned-section {
		margin-top: 8px;
	}

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
		.paper-title {
			font-size: 1rem;
		}

		.paper-meta {
			font-size: 0.85rem;
		}
	}
</style>
