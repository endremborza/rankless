<script lang="ts">
	import type { Paper, EntityAttsForLinks } from '$lib/tree-types';
	import { toBibtexFile, type CitationStyle } from '$lib/utils/reference-format';
	import { copyToClipboard, downloadTextFile } from '$lib/utils/clipboard-download';
	import { COMPLETE_YEAR, LATEST_YEAR } from '$lib/constants';

	export let filteredPapers: Paper[];
	export let totalCount: number;
	export let entityAtts: EntityAttsForLinks;
	export let discAuthorNames: Record<string, string>;

	export let sortBy: 'year' | 'citations' = 'year';
	export let minCitations = 0;
	export let minYear = COMPLETE_YEAR;
	export let topN = 0;
	export let citationStyle: CitationStyle = 'html';

	function handleCopyBibtex() {
		copyToClipboard(toBibtexFile(filteredPapers, entityAtts, discAuthorNames));
	}

	function handleDownloadBibtex() {
		downloadTextFile('papers.bib', toBibtexFile(filteredPapers, entityAtts, discAuthorNames));
	}

	$: isFiltered = minCitations > 0 || minYear > 0 || topN > 0;
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

		<label title="Hide papers published before this year">
			Since:
			<input
				type="number"
				min={COMPLETE_YEAR}
				max={LATEST_YEAR}
				bind:value={minYear}
				placeholder="year"
				class="num-input year-input"
			/>
		</label>

		<label title="Show only top N papers by citation count (0 = all)">
			Top N:
			<input type="number" min="0" bind:value={topN} placeholder="all" class="num-input" />
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

	{#if isFiltered}
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
		font-size: var(--text-sm);
	}

	select,
	.num-input {
		margin-left: 0.2rem;
		font-size: var(--text-sm);
		padding: 2px 4px;
	}

	.num-input {
		width: 50px;
	}

	.year-input {
		width: 66px;
	}

	button {
		font-size: var(--text-xs);
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
		font-size: var(--text-xs);
		opacity: 0.5;
	}

	@media (min-width: 1200px) {
		.controls {
			font-size: var(--text-base);
		}

		select,
		.num-input {
			font-size: var(--text-base);
		}

		button {
			font-size: var(--text-base);
			padding: 4px 12px;
		}
	}
</style>
