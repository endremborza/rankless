<script lang="ts">
	export let summaryLabel = 'What are hit papers?';
</script>

<details class="hit-paper-explainer">
	<summary>{summaryLabel}</summary>
	<p>
		Hit papers significantly outperform the citation benchmark for their cohort. A paper qualifies
		if <strong>any</strong> of the following hold:
	</p>
	<ul>
		<li>it has ≥500 total citations;</li>
		<li>
			it reaches ≥1.5× the top-1% citation threshold for papers in the same subfield and year (the
			threshold is the <em>minimum</em> needed to enter the top 1%, not the average within it);
		</li>
		<li>it reaches the top citation threshold in at least one of its specific research topics.</li>
	</ul>
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

	.hit-paper-explainer ul {
		margin: 6px 0 0;
		padding-left: 22px;
		line-height: 1.4;
	}

	.hit-paper-explainer li {
		margin-bottom: 4px;
	}
</style>
