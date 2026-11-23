<script lang="ts">
	import { paperHref, type PaperCard } from '$lib/utils/impact-highlights';
	import { othersLabel } from '$lib/utils/paper-helpers';
	import HighlightMark from './HighlightMark.svelte';

	export let card: PaperCard;

	// Bound strings, not literal markup: Svelte trims the whitespace of template text.
	const dot = ' · ';
	const sep = ', ';
	const gap = ' ';

	$: paper = card.paper;
	$: href = paperHref(paper);
</script>

{#if href}<a class="title" {href}>{@html paper.name}</a>{:else}<span class="title"
		>{@html paper.name}</span
	>{/if}
<div class="line">
	<span class="year">{paper.year}</span>{#each card.facts as m, i (i)}{dot}<HighlightMark
			mark={m}
		/>{/each}
</div>
{#if card.people.length > 0}
	<div class="line">
		{#each card.people as m, i (i)}{#if i > 0}{sep}{/if}<HighlightMark
				mark={m}
			/>{/each}{#if card.others > 0}{gap}<span class="others">{othersLabel(card.others)}</span>{/if}
	</div>
{/if}
{#each card.institutions as m, i (i)}
	<div class="line"><HighlightMark mark={m} /></div>
{/each}

<style>
	.title {
		font-size: var(--text-sm);
		font-weight: 600;
		line-height: 1.25;
		color: var(--color-text);
		text-decoration: none;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	a.title:hover {
		text-decoration: underline;
	}

	.line {
		font-size: var(--text-xs);
		line-height: 1.6;
	}

	.year {
		opacity: 0.7;
	}

	.others {
		opacity: 0.7;
	}
</style>
