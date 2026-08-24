<script lang="ts">
	import type { PageData } from './$types';
	import SessionFindings from '$lib/components/SessionFindings.svelte';
	import { isGenerationMeta } from '$lib/mcp-util';
	export let data: PageData;
	$: ({ session, findings, command } = data);
	$: meta = session.meta;
	const RAW = ['report.md', 'reproduce.md', 'findings.json'];
</script>

<svelte:head>
	<title>{session.title ?? session.name} — Rankless exploration</title>
</svelte:head>

<article class="run">
	<p class="crumbs"><a href="/mcp">← all sessions &amp; MCP docs</a></p>
	<h1>{session.title ?? session.name}</h1>

	{#if meta && isGenerationMeta(meta)}
		<p class="meta">
			{meta.backend} data · {meta.model} · {meta.counts.accepted}/{meta.counts.targets} accepted ·
			{meta.counts.stored} in store · {meta.generated}
		</p>
	{:else if meta}
		<p class="meta">
			{meta.backend} data · {meta.model} · foci {meta.foci.join(', ')} ·
			{meta.counts.metricsReproduced}/{meta.counts.metrics} numbers reproduced · mined in {Math.round(
				meta.runtimeSeconds.mine
			)}s · {meta.generated}
		</p>
	{:else}
		<p class="status">Status: <strong>{session.status}</strong></p>
	{/if}

	<div class="command">
		<span>Command</span>
		<code>{command}</code>
	</div>

	{#if session.status === 'failed'}
		<p class="err">This run failed. {session.error ?? ''}</p>
	{:else if !findings}
		<p class="status">
			Run is <strong>{session.status}</strong> — outputs will appear here when it finishes.
		</p>
	{:else}
		<SessionFindings
			findings={findings.findings}
			endpointSuggestions={findings.endpointSuggestions}
		/>
		<p class="raw">
			Raw:
			{#each RAW as f, i (i)}
				<a href="/mcp/runs/{session.name}/raw/{f}">{f}</a>
			{/each}
		</p>
	{/if}
</article>

<style>
	.run {
		max-width: 52rem;
		margin: 0 auto;
		padding: var(--unified-padding);
		line-height: var(--lh-body);
	}
	.crumbs {
		font-size: var(--text-xs);
		color: var(--color-text-light);
	}
	h1 {
		font-size: var(--text-2xl);
		margin: 0.2em 0;
	}
	.meta,
	.status {
		color: var(--color-text-light);
		font-size: var(--text-sm);
	}
	.command {
		margin: 1rem 0;
		display: grid;
		gap: 0.2rem;
	}
	.command span {
		font-size: var(--text-xs);
		color: var(--color-text-light);
	}
	.command code {
		background: rgba(var(--color-range-30), 0.08);
		padding: 0.5em 0.7em;
		border-radius: 4px;
		overflow-x: auto;
		font-family: var(--font-mono);
	}
	.err {
		color: var(--color-graph-pink);
		font-size: var(--text-sm);
	}
	.raw {
		margin-top: 2.5rem;
		display: flex;
		gap: 0.8rem;
		font-size: var(--text-xs);
		color: var(--color-text-light);
	}
</style>
