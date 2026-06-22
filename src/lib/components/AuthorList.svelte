<script lang="ts">
	import type { Paper, EntityAttsForLinks } from '$lib/tree-types';
	import { resolveAuthors } from '$lib/utils/paper-helpers';

	export let paper: Paper;
	export let entityAtts: EntityAttsForLinks = {};
	export let discAuthorNames: Record<string, string> = {};
	// Cap the rendered list, appending "et al." when more authors exist; undefined = show all.
	export let max: number | undefined = undefined;
	export let showInst = false;

	// Bound strings, not literal markup: Svelte trims trailing whitespace inside template text,
	// which would collapse the ", " / " et al." separators back to no-space variants.
	const sep = ', ';
	const etAl = ' et al.';

	// Compact (capped) lists drop unknown co-authors; full lists keep them as "(unknown)".
	$: authors = resolveAuthors(paper, entityAtts, discAuthorNames, max != null);
	$: shown = max != null ? authors.slice(0, max) : authors;
	$: total = paper.authorships.length;
	$: hasMore = total > shown.length;
</script>

{#if shown.length > 0}{#each shown as a, i (i)}{#if i > 0}{sep}{/if}{#if a.url}<a
				class="author-link"
				href={a.url}>{a.name}</a
			>{:else}<span class="author-plain">{a.name}</span>{/if}{#if showInst && a.inst}<span
				class="author-inst"
				>{#if a.instUrl}<a href={a.instUrl}>{a.inst}</a>{:else}{a.inst}{/if}</span
			>{/if}{/each}{#if hasMore}{etAl}{/if}{:else if max != null && total > 0}{total} author{total ===
	1
		? ''
		: 's'}{/if}

<style>
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

	.author-inst {
		opacity: 0.6;
		font-size: 0.9em;
	}

	.author-inst::before {
		content: ' (';
	}

	.author-inst::after {
		content: ')';
	}

	.author-inst a {
		color: inherit;
		text-decoration: none;
		border-bottom: 1px dotted rgba(var(--color-range-15), 0.35);
	}

	.author-inst a:hover {
		border-bottom-style: solid;
	}
</style>
