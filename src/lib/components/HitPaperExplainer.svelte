<script lang="ts">
	export let summaryLabel = 'What are hit papers?';
</script>

<details class="hit-paper-explainer">
	<summary>{summaryLabel}</summary>
	<p>
		Hit papers significantly outperform the citation benchmark for their cohort. A paper qualifies
		if it has ≥500 total citations, achieves ≥1.5× the top-1% citation threshold for papers in the
		same subfield and year (this is the <em>minimum</em> needed to enter the top 1%, not the average
		within it), or reaches the top citation threshold in at least one of its specific research
		topics.
	</p>
</details>

<style>
	.hit-paper-explainer {
		font-size: 0.8rem;
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
