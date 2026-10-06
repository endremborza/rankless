<script lang="ts">
	import type { PaperOut } from '$lib/wire/rankless_server/responses';
	import type { EntityAttsForLinks } from '$lib/wire/rankless_trees/io';
	import {
		resolveSourceName,
		getPaperHighlights,
		hasNobelCoauthor,
		highlightLabel
	} from '$lib/utils/paper-helpers';
	import { createEventDispatcher } from 'svelte';
	import AuthorList from './AuthorList.svelte';

	export let paper: PaperOut | undefined;
	export let wid: number;
	export let entityAtts: EntityAttsForLinks;
	export let discAuthorNames: Record<string, string>;
	export let authorsMeta: Record<string, { prize: number; year: number }> = {};
	export let pageAuthorDmId: string | undefined = undefined;
	export let isHovered = false;
	export let isRelated = false;
	export let dimmed = false;
	export let isExpanded = false;

	const dispatch = createEventDispatcher<{
		toggle: number;
		hover: number;
		leave: void;
	}>();

	const BADGE_CLASS: Record<string, string> = {
		hit: 'hl-hit',
		prestigious: 'hl-prestigious',
		nobel: 'hl-nobel'
	};

	function chipMaxW(): number {
		const len = paper?.name?.length ?? 50;
		return Math.min(380, Math.max(200, 150 + Math.round(len * 2)));
	}

	$: highlights = (() => {
		if (!paper) return [];
		const hl = getPaperHighlights(paper, undefined, entityAtts);
		if (hasNobelCoauthor(paper, authorsMeta, pageAuthorDmId)) hl.push({ key: 'nobel' });
		return hl;
	})();
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_mouse_events_have_key_events -->
<!-- svelte-ignore a11y_click_events_have_key_events -->
<div
	class="chip"
	class:is-hovered={isHovered}
	class:is-related={isRelated}
	class:dimmed
	style="max-width: {chipMaxW()}px"
	on:click={() => dispatch('toggle', wid)}
	on:mouseover={() => dispatch('hover', wid)}
	on:mouseleave={() => dispatch('leave')}
>
	<div class="chip-title" class:clamp={!isExpanded}>
		{#if isExpanded && paper?.doi}
			<a href="https://doi.org/{paper.doi}" target="_blank" rel="noopener"
				>{@html paper?.name ?? '(unknown)'}</a
			>
		{:else}
			{@html paper?.name ?? '(unknown)'}
		{/if}
	</div>
	<div class="chip-sub">
		<span>{paper?.year}</span>
		{#each highlights as hl, __i (__i)}
			{#if BADGE_CLASS[hl.key]}
				<span class="badge {BADGE_CLASS[hl.key]}">{highlightLabel(hl)}</span>
			{/if}
		{/each}
	</div>
	{#if isExpanded && paper}
		{@const source = resolveSourceName(paper.source, entityAtts)}
		{@const sourceSemId = entityAtts.sources?.[String(paper.source)]?.semantic_id}
		<div class="chip-details">
			<span>{paper.citations} citations</span>
			{#if source}
				<span class="sep">·</span>
				{#if sourceSemId}
					<a href="/sources/{sourceSemId}">{source}</a>
				{:else}
					<span class="source-name">{source}</span>
				{/if}
			{/if}
			{#if paper.authorships.length > 0}
				<div class="chip-authors">
					<AuthorList {paper} {entityAtts} {discAuthorNames} max={3} showInst />
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.chip {
		padding: 6px 10px;
		font-size: var(--text-sm);
		line-height: var(--lh-ui);
		border-radius: 4px;
		border: 1px solid rgba(var(--color-range-15), 0.15);
		background: rgba(var(--color-range-15), 0.03);
		cursor: pointer;
		transition:
			border-color 160ms,
			background-color 160ms,
			opacity 160ms;
		position: relative;
	}

	.chip.dimmed {
		opacity: 0.35;
	}

	.chip.is-hovered {
		border-color: var(--color-theme-blue);
		background: rgba(var(--color-range-15), 0.08);
		box-shadow: 0 0 0 1px var(--color-theme-blue);
	}

	.chip.is-related {
		border-color: var(--color-theme-blue);
		background: rgba(var(--color-range-15), 0.06);
	}

	.chip-title {
		font-weight: 600;
		line-height: 1.2;
	}

	.chip-title.clamp {
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.chip-title a {
		color: inherit;
		text-decoration: none;
	}

	.chip-title a:hover {
		text-decoration: underline;
	}

	.chip-sub {
		display: flex;
		align-items: center;
		gap: 4px;
		font-size: var(--text-xs);
	}

	.chip-details {
		font-size: var(--text-xs);
		opacity: 0.7;
		margin-top: 4px;
		padding-top: 4px;
		border-top: 1px solid rgba(var(--color-range-15), 0.1);
	}

	.chip-details a {
		color: inherit;
		text-decoration: none;
	}

	.chip-details a:hover {
		text-decoration: underline;
	}

	.source-name {
		font-style: italic;
	}

	.chip-authors {
		margin-top: 2px;
	}

	.badge {
		display: inline-block;
		padding: 1px 5px;
		border-radius: 3px;
		font-size: var(--text-2xs);
		font-weight: 700;
		letter-spacing: 0.03em;
		text-transform: uppercase;
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
		.chip {
			padding: 8px 12px;
			font-size: var(--text-lg);
			flex-basis: 300px;
		}

		.chip-sub {
			font-size: var(--text-base);
		}

		.badge {
			font-size: var(--text-sm);
			padding: 1px 6px;
		}

		.chip-details {
			font-size: var(--text-sm);
		}
	}

	.sep {
		margin: 0 3px;
	}
</style>
