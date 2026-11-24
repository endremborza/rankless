<script lang="ts">
	import type { ReviewVerdict } from '$lib/types/review';

	export let verdict: ReviewVerdict;

	$: checkLines = Object.entries(verdict.checks ?? {})
		.filter(([, v]) => v !== null && v !== '' && !(Array.isArray(v) && v.length === 0))
		.map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : String(v)}`);
</script>

<details class="verdict">
	<summary class={verdict.verdict}>
		AI: {verdict.verdict} · {Math.round(verdict.confidence * 100)}%
	</summary>
	<div class="body">
		<p>{verdict.reasoning}</p>
		{#each checkLines as line, i (i)}
			<p class="check">{line}</p>
		{/each}
		<p class="meta">{verdict.model} · {verdict.created_at}</p>
	</div>
</details>

<style>
	.verdict {
		font-size: var(--text-xs);
	}
	summary {
		cursor: pointer;
		white-space: nowrap;
		border-radius: 0.6rem;
		padding: 0.05rem 0.5rem;
		display: inline-block;
		color: var(--tone);
		background: color-mix(in srgb, var(--tone) 15%, transparent);
	}
	summary.approve {
		--tone: var(--color-ok);
	}
	summary.reject {
		--tone: var(--color-err);
	}
	summary.unsure {
		--tone: var(--color-warn);
	}
	.body {
		max-width: 26rem;
		padding: 0.3rem 0.2rem;
	}
	.body p {
		margin: 0.2rem 0;
	}
	.check,
	.meta {
		color: var(--color-text-light);
	}
	.meta {
		font-family: var(--font-mono);
	}
</style>
