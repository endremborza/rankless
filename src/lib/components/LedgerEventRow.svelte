<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import VerdictBadge from './VerdictBadge.svelte';
	import type { AdminReviewRow } from '$lib/types/review';

	export let row: AdminReviewRow;
	export let selected: boolean;
	export let busy: boolean;

	const dispatch = createEventDispatcher<{
		toggle: number;
		moderate: { event_ids: number[]; decision: 'accepted' | 'rejected' };
	}>();

	$: actionable = row.moderation === 'pending_review' && row.revoked_at === null;
</script>

<tr class:pending={row.moderation === 'pending_review'} class:revoked={row.revoked_at !== null}>
	<td>
		{#if actionable}
			<input
				type="checkbox"
				checked={selected}
				on:change={() => dispatch('toggle', row.event_id)}
			/>
		{/if}
	</td>
	<td>{row.event_id}</td>
	<td>{row.kind}</td>
	<td class="subject">
		{#if row.work?.title}
			<span class="title">{row.work.title}</span>
			{#if row.work.year}<span class="muted"> ({row.work.year})</span>{/if}
			{#if row.work.venue}<span class="muted"> · {row.work.venue}</span>{/if}
		{:else}
			{row.summary}
		{/if}
		<span class="links">
			{#if row.work?.doi}
				<a href="https://doi.org/{row.work.doi}" target="_blank" rel="noopener">doi</a>
			{/if}
			{#if row.work?.oa_work_id}
				<a href="https://openalex.org/works/{row.work.oa_work_id}" target="_blank" rel="noopener"
					>openalex</a
				>
			{/if}
		</span>
		{#if row.work && !row.work.enriched}
			<span class="muted">· metadata not fetched</span>
		{/if}
	</td>
	<td class="mono">{row.created_at}</td>
	<td>
		{row.moderation}{row.revoked_at ? ' · revoked' : ''}
		{#if row.auto_moderated}
			<span class="auto" title={row.moderated_by}>auto</span>
		{:else if row.moderated_by}
			<span class="muted">· by {row.moderated_by}</span>
		{/if}
	</td>
	<td class={row.pipeline.cls}>{row.pipeline.label}</td>
	<td>
		{#if row.hard?.conclusive}
			<span class="proven" title="claimant ORCID in {row.hard.sources.join(' + ')} authorship"
				>proven</span
			>
		{:else if row.verdict}
			<VerdictBadge verdict={row.verdict} />
		{/if}
	</td>
	<td class="actions">
		{#if actionable}
			<button
				class="control ok"
				disabled={busy}
				on:click={() => dispatch('moderate', { event_ids: [row.event_id], decision: 'accepted' })}
				>Approve</button
			>
			<button
				class="control no"
				disabled={busy}
				on:click={() => dispatch('moderate', { event_ids: [row.event_id], decision: 'rejected' })}
				>Reject</button
			>
		{/if}
	</td>
</tr>

<style>
	td {
		text-align: left;
		padding: 0.4rem 0.5rem;
		border-bottom: 1px solid rgba(var(--color-range-30), 0.15);
		vertical-align: top;
	}
	.subject {
		max-width: 34rem;
	}
	.title {
		font-weight: 500;
	}
	.links a {
		margin-left: 0.35rem;
		font-size: var(--text-xs);
	}
	.mono {
		font-family: var(--font-mono);
		font-size: var(--text-sm);
		white-space: nowrap;
	}
	.muted,
	.awaiting {
		color: var(--color-text-light);
	}
	.auto,
	.proven {
		border-radius: 0.6rem;
		padding: 0.05rem 0.5rem;
		font-size: var(--text-xs);
		white-space: nowrap;
	}
	.auto {
		color: var(--highlight-text);
		background: rgba(var(--color-range-30), 0.15);
	}
	.proven {
		color: var(--color-ok);
		background: color-mix(in srgb, var(--color-ok) 15%, transparent);
	}
	.applied {
		color: var(--color-ok);
		font-weight: bold;
	}
	.skipped {
		color: var(--color-warn);
	}
	tr.pending {
		background: rgba(var(--color-range-90), 0.12);
	}
	tr.revoked {
		opacity: 0.55;
		text-decoration: line-through;
	}
	.actions {
		white-space: nowrap;
	}
	button {
		margin-right: 0.3rem;
	}
	button:disabled {
		cursor: default;
		opacity: 0.5;
	}
	button.ok {
		color: var(--color-ok);
	}
	button.no {
		color: var(--color-err);
	}
</style>
