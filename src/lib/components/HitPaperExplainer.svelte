<script lang="ts">
	import type { HitRule } from '$lib/tree-types';
	import { formatNumber, formatShare, trimZeros } from '$lib/text-format-util';

	// The rule the pipeline actually ran with, from `/methodology` via the (stat) layout load. Every
	// number below is read from it, so this text cannot drift from the data behind it — and with no
	// rule to read there is nothing to say, so the component renders nothing.
	export let rule: HitRule | null;
	export let summaryLabel = 'What are hit papers?';
</script>

{#if rule}
	<details class="hit-paper-explainer">
		<summary>{summaryLabel}</summary>
		<p>
			Hit papers significantly outperform the citation benchmark for their cohort. The benchmark is
			the minimum citation count needed to enter the top {formatShare(rule.topPctile)}, blended from
			the paper's own subfield and year together ({formatShare(rule.wSfYear)}), its year alone ({formatShare(
				rule.wYear
			)}) and its subfield alone ({formatShare(rule.wSf)}); a subfield and year with fewer than {formatNumber(
				rule.sfYearMinPapers
			)} papers takes its year's benchmark in place of its own. A paper needs at least {rule.minNeeded}
			citations, and then qualifies if <strong>any</strong> of the following hold:
		</p>
		<ul>
			<li>it has ≥{formatNumber(rule.minUniversal)} total citations;</li>
			<li>it reaches ≥{trimZeros(rule.scoreThreshold)}× that benchmark;</li>
			<li>it is among the {rule.topTopic} most cited papers of one of its research topics;</li>
			<li>
				it originates one of its research topics: it is the topic's earliest paper, from {rule.creatorCutoffYear}
				or later, with at least {rule.minCreatorCitations} citations.
			</li>
		</ul>
		<p>
			A paper published no later than the year one of its authors won a Nobel prize counts
			{trimZeros(rule.nobelMultiplier)}× against the benchmark. Papers from {screen.finalYear} are not
			counted yet.
		</p>
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

	.hit-paper-explainer ul {
		margin: 6px 0 0;
		padding-left: 22px;
		line-height: 1.4;
	}

	.hit-paper-explainer li {
		margin-bottom: 4px;
	}
</style>
