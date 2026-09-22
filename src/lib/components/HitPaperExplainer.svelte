<script lang="ts">
	import { page } from '$app/state';

	// The texts are the backend's, filled from the constants the pipeline ran with, so they cannot
	// drift from the data behind them; with none to read there is nothing to say and nothing renders.

	export let summaryLabel = 'What are hit papers?';
</script>

{#if page.data.methodology}
	<details class="hit-paper-explainer">
		<summary>{summaryLabel}</summary>
		{#each page.data.methodology.texts as text, i (i)}
			<p><strong>{text.label}:</strong> {text.meaning}</p>
		{/each}
	</details>
{/if}

<style>
	.hit-paper-explainer {
		font-size: var(--text-sm);
		opacity: 0.8;
	}

	.hit-paper-explainer summary {
		cursor: pointer;
		font-weight: 600;
		padding: 4px 0;
	}

	.hit-paper-explainer p {
		margin-top: 6px;
		line-height: 1.4;
		padding-left: 4px;
	}
</style>
