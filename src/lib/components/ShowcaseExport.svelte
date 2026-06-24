<script lang="ts">
	import type { ShowcaseSamplePaper } from '$lib/types/showcase';
	import { formatReference, toBibtexFile, type CitationStyle } from '$lib/utils/reference-format';
	import { copyToClipboard, downloadTextFile } from '$lib/utils/clipboard-download';

	export let data: ShowcaseSamplePaper;

	const STYLES: { value: CitationStyle; label: string }[] = [
		{ value: 'html', label: 'HTML' },
		{ value: 'chicago', label: 'Chicago' },
		{ value: 'apa', label: 'APA' },
		{ value: 'mla', label: 'MLA' }
	];

	let style: CitationStyle = 'html';

	$: reference = formatReference(data.paper, data.entityAtts, data.discAuthorNames, style);
	$: bibtex = toBibtexFile([data.paper], data.entityAtts, data.discAuthorNames);
</script>

<div class="export-preview">
	<label class="style-pick">
		Style:
		<select bind:value={style}>
			{#each STYLES as s (s.value)}
				<option value={s.value}>{s.label}</option>
			{/each}
		</select>
	</label>

	<div class="reference">
		{#if style === 'html'}
			{@html reference}
		{:else}
			{reference}
		{/if}
	</div>

	<div class="actions">
		<button on:click={() => copyToClipboard(bibtex)}>Copy BibTeX</button>
		<button on:click={() => downloadTextFile('paper.bib', bibtex)}>Download .bib</button>
	</div>
</div>

<style>
	.export-preview {
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.style-pick {
		font-size: var(--text-sm);
		opacity: 0.8;
	}

	.style-pick select {
		margin-left: 0.3rem;
		font-size: var(--text-sm);
		padding: 2px 4px;
	}

	.reference {
		font-size: var(--text-sm);
		line-height: 1.5;
		padding: 12px 14px;
		min-height: 4.5em;
		background: rgba(var(--color-range-15), 0.04);
		border: 1px solid rgba(var(--color-range-15), 0.12);
		overflow-wrap: anywhere;
	}

	.reference :global(a) {
		color: inherit;
	}

	.reference :global(em) {
		font-style: italic;
	}

	.actions {
		display: flex;
		gap: 8px;
		flex-wrap: wrap;
	}

	.actions button {
		font-size: var(--text-xs);
		padding: 4px 12px;
		border-radius: 3px;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		background: none;
		cursor: pointer;
		color: var(--color-text);
		font-family: inherit;
	}

	.actions button:hover {
		background: rgba(var(--color-range-15), 0.06);
	}
</style>
