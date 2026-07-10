<script lang="ts">
	import type { SessionFinding, McpEndpointIdea } from '$lib/types/mcp';
	import { entPath } from '$lib/mcp-util';

	export let findings: SessionFinding[];
	export let endpointSuggestions: McpEndpointIdea[] = [];

	const FOCI = ['share', 'query', 'data-issue'];

	const badge = (f: SessionFinding): string => {
		if (!f.metrics.length) return '— no numbers';
		const bad = f.metrics.filter((m) => !m.ok).length;
		return bad ? `✗ ${bad} unverified` : '✓ reproduced';
	};
	const cell = (m: SessionFinding['metrics'][number]): string => {
		if (m.error) return `⚠️ ${m.error}`;
		if (m.claimed !== null && String(m.claimed) !== String(m.reproduced))
			return `${m.reproduced} (model claimed ${m.claimed})`;
		return String(m.reproduced);
	};
</script>

{#each FOCI as focus, fi (fi)}
	{@const group = findings.filter((f) => f.focus === focus)}
	{#if group.length}
		<h2>{focus} <span class="count">({group.length})</span></h2>
		{#each group as f, i (i)}
			<div class="finding">
				<h3>
					{f.title}
					<code class="mk">{badge(f)}</code>
					{#if f.share_kind || f.issue_kind}
						<span class="tag">{f.share_kind ?? f.issue_kind}</span>
					{/if}
				</h3>
				{#if f.question}<p class="q"><strong>Q:</strong> {f.question}</p>{/if}
				<p>{f.description}</p>
				{#if f.ledger_suggestion}
					<p class="ledger">
						<strong>Ledger fix:</strong> <code>{f.ledger_suggestion.kind}</code> —
						{f.ledger_suggestion.note}
					</p>
				{/if}
				{#if f.metrics.length}
					<table>
						<tbody>
							{#each f.metrics as m, j (j)}
								<tr>
									<th>{m.label}</th>
									<td>{cell(m)}</td>
									<td class="prov"><code>{m.tool}</code> → <code>{m.path}</code></td>
								</tr>
							{/each}
						</tbody>
					</table>
				{/if}
				{#if f.entities.length}
					<p class="ents">
						{#each f.entities as e, j (j)}
							<a href={entPath(e)}>{entPath(e)}</a>
						{/each}
					</p>
				{/if}
			</div>
		{/each}
	{/if}
{/each}

{#if endpointSuggestions.length}
	<h2>Endpoints the agent wished for</h2>
	<ul class="ideas">
		{#each endpointSuggestions as idea, i (i)}
			<li><code>{idea.name}</code> — {idea.unlocks}</li>
		{/each}
	</ul>
{/if}

<style>
	h2 {
		font-size: var(--text-xl);
		border-bottom: 2px solid rgba(var(--color-range-30), 0.35);
		padding-bottom: 0.2em;
		margin-top: 2rem;
	}
	h2 .count {
		color: var(--color-text-light);
		font-weight: normal;
	}
	.finding {
		border-left: 3px solid rgba(var(--color-range-30), 0.4);
		padding-left: 1rem;
		margin: 1.4rem 0;
	}
	.finding h3 {
		font-size: var(--text-lg);
		margin-bottom: 0.3em;
	}
	.mk {
		font-size: var(--text-xs);
		color: var(--color-text-light);
	}
	.tag {
		font-size: var(--text-2xs);
		color: var(--color-text-light);
		border: 1px solid var(--color-theme-lightgrey);
		border-radius: 10px;
		padding: 0.1em 0.6em;
		margin-left: 0.3em;
		vertical-align: middle;
	}
	.q {
		color: var(--color-text-light);
	}
	.ledger {
		font-size: var(--text-sm);
	}
	table {
		border-collapse: collapse;
		font-size: var(--text-sm);
		margin: 0.6rem 0;
	}
	th {
		text-align: left;
		font-weight: normal;
		padding: 0.15em 1em 0.15em 0;
	}
	td {
		padding: 0.15em 1em 0.15em 0;
		font-variant-numeric: tabular-nums;
	}
	.prov {
		font-size: var(--text-2xs);
		color: var(--color-text-light);
	}
	.ents {
		display: flex;
		flex-wrap: wrap;
		gap: 0.6rem;
		font-size: var(--text-xs);
	}
	.ideas {
		font-size: var(--text-sm);
	}
	code {
		font-family: var(--font-mono);
	}
</style>
