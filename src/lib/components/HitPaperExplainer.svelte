<script lang="ts">
	import { METHODOLOGY } from '$lib/wire/rankless_server/responses';

	// The texts are filled from the constants the pipeline runs with, so they cannot drift from the
	// data behind them.

	export let summaryLabel = 'What are hit papers?';
</script>

<details class="hit-paper-explainer">
	<summary>{summaryLabel}</summary>
	{#each METHODOLOGY.texts as text, i (i)}
		<p><strong>{text.label}:</strong> {text.meaning}</p>
	{/each}
</details>

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
