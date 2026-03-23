<script lang="ts">
	import type { Paper, EntityAttsForLinks } from '$lib/tree-types';
	import {
		resolveSourceName,
		getChipAuthors,
		getPaperHighlights,
		type PaperHighlight
	} from '$lib/utils/paper-helpers';
	import { createEventDispatcher } from 'svelte';

	export let paper: Paper | undefined;
	export let wid: number;
	export let entityAtts: EntityAttsForLinks;
	export let discAuthorNames: Record<string, string>;
	export let authorsMeta: Record<string, { prize: number; year: number }> = {};
	export let pageAuthorDmId: string | undefined = undefined;
	export let pageAuthorIsNobel = false;
	export let isHovered = false;
	export let isRelated = false;
	export let dimmed = false;
	export let isExpanded = false;

	const dispatch = createEventDispatcher<{
		toggle: number;
		hover: number;
		leave: void;
	}>();

	const HIGHLIGHT_DEFS: Record<string, { label: string; cls: string }> = {
		hit: { label: 'Hit', cls: 'hl-hit' },
		prestigious: { label: 'Prestigious', cls: 'hl-prestigious' },
		nobel: { label: 'Nobel', cls: 'hl-nobel' }
	};

	function badgeLabel(hl: PaperHighlight): string {
		if (hl.key === 'prestigious' && hl.label) return hl.label;
		return HIGHLIGHT_DEFS[hl.key]?.label ?? hl.key;
	}

	function chipMaxW(): number {
		const len = paper?.name?.length ?? 50;
		return Math.min(380, Math.max(200, 150 + Math.round(len * 2)));
	}

	function hasNobelCoauthor(p: Paper): boolean {
		for (const ship of p.authorships) {
			if (ship.author[0] !== 'F') continue;
			const dmId = ship.author.slice(1);
			if (pageAuthorIsNobel && dmId === pageAuthorDmId) continue;
			if ((authorsMeta[dmId]?.prize ?? 0) > 0) return true;
		}
		return false;
	}

	$: highlights = (() => {
		if (!paper) return [];
		const hl = getPaperHighlights(paper, undefined, entityAtts);
		if (hasNobelCoauthor(paper)) hl.push({ key: 'nobel' });
		return hl;
	})();
</script>

<!-- svelte-ignore a11y-no-static-element-interactions -->
<!-- svelte-ignore a11y-mouse-events-have-key-events -->
<!-- svelte-ignore a11y-click-events-have-key-events -->
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
		{#each highlights as hl}
			{#if HIGHLIGHT_DEFS[hl.key]}
				<span class="badge {HIGHLIGHT_DEFS[hl.key].cls}">{badgeLabel(hl)}</span>
			{/if}
		{/each}
	</div>
	{#if isExpanded && paper}
		{@const source = resolveSourceName(paper.source, entityAtts)}
		{@const sourceSemId = entityAtts.sources?.[String(paper.source)]?.semantic_id}
		{@const authors = getChipAuthors(paper, entityAtts, discAuthorNames, 3)}
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
			{#if authors.length > 0}
				<div class="chip-authors">
					{#each authors as author, ai}
						{#if ai > 0},&nbsp;{/if}
						{#if author.url}
							<a href={author.url}>{author.name}</a>
						{:else}
							{author.name}
						{/if}
					{/each}
					{#if paper.authorships.length > authors.length}
						&nbsp;et al.
					{/if}
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.chip {
		padding: 6px 10px;
		font-size: 0.78rem;
		line-height: 1.3;
		border-radius: 4px;
		border: 1px solid rgba(var(--color-range-15), 0.15);
		background: rgba(var(--color-range-15), 0.03);
		cursor: pointer;
		transition: border-color 160ms, background-color 160ms, opacity 160ms;
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
		font-size: 0.65rem;
	}

	.chip-details {
		font-size: 0.65rem;
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
		font-size: 0.55rem;
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
			font-size: 1.15rem;
			flex-basis: 300px;
		}

		.chip-sub {
			font-size: 0.9rem;
		}

		.badge {
			font-size: 0.8rem;
			padding: 1px 6px;
		}

		.chip-details {
			font-size: 0.82rem;
		}
	}

	.sep {
		margin: 0 3px;
	}
</style>
