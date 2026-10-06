<script lang="ts">
	import type { PaperOut } from '$lib/wire/rankless_server/responses';
	import type { EntityAttsForLinks } from '$lib/wire/rankless_trees/io';
	import { authorByline, othersLabel, resolveAuthors } from '$lib/utils/paper-helpers';

	export let paper: PaperOut;
	export let entityAtts: EntityAttsForLinks = {};
	export let discAuthorNames: Record<string, string> = {};
	// Named authors shown before "+N others", which expands to every served name.
	export let max = 8;
	export let showInst = false;

	// The paper whose list is expanded, so a reused instance starts collapsed on another paper.
	let expandedWid: number | null = null;

	// Bound strings, not literal markup: Svelte trims trailing whitespace inside template text,
	// which would collapse the ", " / " " separators back to no-space variants.
	const sep = ', ';
	const gap = ' ';

	$: authors = resolveAuthors(paper, entityAtts, discAuthorNames);
	$: expanded = expandedWid === paper.wid;
	$: byline = authorByline(authors, paper.authorCount, max, expanded);
</script>

{#if byline.shown.length > 0}{#each byline.shown as a, i (i)}{#if i > 0}{sep}{/if}{#if a.url}<a
				class="author-link"
				href={a.url}>{a.name}</a
			>{:else}<span class="author-plain">{a.name}</span>{/if}{#if showInst && a.inst}<span
				class="author-inst"
				>{#if a.instUrl}<a href={a.instUrl}>{a.inst}</a>{:else}{a.inst}{/if}</span
			>{/if}{/each}{#if byline.others > 0}{gap}{#if byline.expandable}<button
				type="button"
				class="author-toggle"
				on:click|stopPropagation={() => (expandedWid = paper.wid)}
				>{othersLabel(byline.others)}</button
			>{:else}<span class="author-others">{othersLabel(byline.others)}</span
			>{/if}{/if}{#if expanded}{gap}<button
			type="button"
			class="author-toggle"
			on:click|stopPropagation={() => (expandedWid = null)}>fewer</button
		>{/if}{:else if paper.authorCount > 0}{paper.authorCount.toLocaleString('en-US')} author{paper.authorCount ===
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

	.author-others {
		white-space: nowrap;
		opacity: 0.6;
	}

	.author-toggle {
		font: inherit;
		color: inherit;
		background: none;
		border: none;
		padding: 0;
		cursor: pointer;
		white-space: nowrap;
		opacity: 0.6;
		border-bottom: 1px dotted rgba(var(--color-range-15), 0.45);
	}

	.author-toggle:hover {
		opacity: 1;
	}
</style>
