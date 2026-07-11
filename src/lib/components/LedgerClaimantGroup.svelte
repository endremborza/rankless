<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import LedgerEventRow from './LedgerEventRow.svelte';
	import MaybeLink from './MaybeLink.svelte';
	import OrcidLink from './OrcidLink.svelte';
	import type { AdminReviewRow } from '$lib/types/review';

	export let rows: AdminReviewRow[]; // all rows share one actor orcid
	export let selected: Set<number>;
	export let busy: Set<number>;

	const dispatch = createEventDispatcher<{
		toggle: number;
		toggleGroup: { event_ids: number[]; on: boolean };
		moderate: { event_ids: number[]; decision: 'accepted' | 'rejected' };
	}>();

	$: head = rows[0];
	$: actionableIds = rows
		.filter((r) => r.moderation === 'pending_review' && r.revoked_at === null)
		.map((r) => r.event_id);
	$: allSelected = actionableIds.length > 0 && actionableIds.every((id) => selected.has(id));
	$: pendingCount = actionableIds.length;
</script>

<details class="group" open>
	<summary>
		<span class="who">
			{#if head.actor_name}
				<MaybeLink
					semanticId={head.actor_semantic_id ?? ''}
					name={head.actor_name}
					rootType="authors"
				/>
			{:else}
				<span class="muted">unknown name</span>
			{/if}
			<OrcidLink orcid={head.orcid} />
		</span>
		<span class="counts">
			{rows.length}
			{rows.length === 1 ? 'event' : 'events'}{pendingCount ? ` · ${pendingCount} pending` : ''}
		</span>
	</summary>
	<table>
		<thead>
			<tr>
				<th>
					{#if actionableIds.length > 0}
						<input
							type="checkbox"
							title="select all pending"
							checked={allSelected}
							on:change={() =>
								dispatch('toggleGroup', { event_ids: actionableIds, on: !allSelected })}
						/>
					{/if}
				</th>
				<th>#</th>
				<th>kind</th>
				<th>subject</th>
				<th>created</th>
				<th>status</th>
				<th>pipeline</th>
				<th>evidence</th>
				<th></th>
			</tr>
		</thead>
		<tbody>
			{#each rows as row, i (i)}
				<LedgerEventRow
					{row}
					selected={selected.has(row.event_id)}
					busy={busy.has(row.event_id)}
					on:toggle
					on:moderate
				/>
			{/each}
		</tbody>
	</table>
</details>

<style>
	.group {
		margin-bottom: 0.8rem;
		border: 1px solid #eee;
		border-radius: 6px;
	}
	summary {
		cursor: pointer;
		padding: 0.5rem 0.7rem;
		display: flex;
		align-items: baseline;
		gap: 0.8rem;
		flex-wrap: wrap;
	}
	.who {
		font-weight: 600;
		display: inline-flex;
		gap: 0.5rem;
		align-items: baseline;
	}
	.counts {
		color: #666;
		font-size: 0.85rem;
	}
	.muted {
		color: #999;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.85rem;
	}
	th {
		text-align: left;
		padding: 0.4rem 0.5rem;
		border-bottom: 1px solid #eee;
	}
</style>
