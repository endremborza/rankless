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
				class="ok"
				disabled={busy}
				on:click={() => dispatch('moderate', { event_ids: [row.event_id], decision: 'accepted' })}
				>Approve</button
			>
			<button
				class="no"
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
		border-bottom: 1px solid #eee;
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
		font-size: 0.75rem;
	}
	.mono {
		font-family: monospace;
		font-size: 0.8rem;
		white-space: nowrap;
	}
	.muted {
		color: #999;
	}
	.auto {
		background: #e7ecfb;
		color: #2a4bb5;
		border-radius: 0.6rem;
		padding: 0.05rem 0.5rem;
		font-size: 0.75rem;
	}
	.proven {
		background: #e2f4e6;
		color: #0a7d28;
		border-radius: 0.6rem;
		padding: 0.05rem 0.5rem;
		font-size: 0.8rem;
		white-space: nowrap;
	}
	.applied {
		color: #0a7d28;
		font-weight: bold;
	}
	.skipped {
		color: #b06a00;
	}
	.awaiting {
		color: #555;
	}
	tr.pending {
		background: #fff7e6;
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
		cursor: pointer;
	}
	button:disabled {
		cursor: default;
		opacity: 0.5;
	}
	button.ok {
		color: #0a7d28;
	}
	button.no {
		color: #b00020;
	}
</style>
