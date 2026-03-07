<script lang="ts">
	import type { Paper, EntityAttsForLinks } from '$lib/tree-types';
	import {
		toBibtexFile,
		type CitationStyle
	} from '$lib/utils/reference-format';
	import { copyToClipboard, downloadTextFile } from '$lib/utils/clipboard-download';

	export let filteredPapers: Paper[];
	export let totalCount: number;
	export let entityAtts: EntityAttsForLinks;
	export let discAuthorNames: Record<string, string>;

	export let sortBy: 'year' | 'citations' = 'year';
	export let minCitations = 0;
	export let citationStyle: CitationStyle = 'html';

	function handleCopyBibtex() {
		copyToClipboard(toBibtexFile(filteredPapers, entityAtts, discAuthorNames));
	}

	function handleDownloadBibtex() {
		downloadTextFile('papers.bib', toBibtexFile(filteredPapers, entityAtts, discAuthorNames));
	}
</script>

<div class="export-controls">
	<div class="controls">
		<label>
			Sort:
			<select bind:value={sortBy}>
				<option value="year">Year</option>
				<option value="citations">Citations</option>
			</select>
		</label>

		<label>
			Min cites:
			<input type="number" min="0" bind:value={minCitations} class="num-input" />
		</label>

		<label>
			Style:
			<select bind:value={citationStyle}>
				<option value="html">HTML</option>
				<option value="chicago">Chicago</option>
				<option value="apa">APA</option>
				<option value="mla">MLA</option>
			</select>
		</label>

		<button on:click={handleCopyBibtex}>Copy BibTeX</button>
		<button on:click={handleDownloadBibtex}>Download .bib</button>
	</div>

	{#if minCitations > 0}
		<span class="filter-note">{filteredPapers.length} of {totalCount} papers shown</span>
	{/if}
</div>

<style>
	.export-controls {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}

	.controls {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem;
		align-items: center;
		font-size: 0.75rem;
	}

	select, .num-input {
		margin-left: 0.2rem;
		font-size: 0.75rem;
		padding: 2px 4px;
	}

	.num-input {
		width: 50px;
	}

	button {
		font-size: 0.7rem;
		padding: 3px 10px;
		border-radius: 3px;
		border: 1px solid rgba(var(--color-range-15), 0.2);
		background: none;
		cursor: pointer;
		color: var(--color-text);
	}

	button:hover {
		background: rgba(var(--color-range-15), 0.06);
	}

	.filter-note {
		font-size: 0.7rem;
		opacity: 0.5;
	}

	@media (min-width: 1200px) {
		.controls {
			font-size: 0.9rem;
		}

		select, .num-input {
			font-size: 0.85rem;
		}

		button {
			font-size: 0.85rem;
			padding: 4px 12px;
		}
	}
</style>
