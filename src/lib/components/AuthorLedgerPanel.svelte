<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import type { LedgerEvent, AppliedManifest } from '$lib/types/ledger';

	export let events: LedgerEvent[];
	export let manifest: AppliedManifest;

	$: appliedIds = new Set(manifest.applied_event_ids);
	$: skippedReasons = new Map(manifest.skipped.map((s) => [s.event_id, s.reason]));

	$: appliedEvents = events.filter(
		(e) =>
			appliedIds.has(e.event_id) &&
			e.revoked_at === null &&
			e.kind !== 'revoke' &&
			e.kind !== 'moderation_decision'
	);
	$: pendingEvents = events.filter(
		(e) => !appliedIds.has(e.event_id) && e.revoked_at === null && e.kind !== 'moderation_decision'
	);

	function describeEvent(e: LedgerEvent): string {
		const p = e.payload;
		switch (p.kind) {
			case 'disown_paper':
				return `Removed: "${p.work.display_snapshot.title || p.work.doi || 'Untitled'}"`;
			case 'claim_paper':
				return `Claimed: ${p.work.doi || p.work.display_snapshot.title || '(no DOI)'}`;
			case 'merge_papers':
				return `Merged "${p.keep.display_snapshot.title || 'Untitled'}" ← "${
					p.drop.display_snapshot.title || 'Untitled'
				}"`;
			case 'merge_authors':
				return `Author merge: drop ${p.drop.display_snapshot.display_name}`;
			case 'revoke':
				return `Revoke of event #${p.target_event_id}`;
			default:
				return e.kind;
		}
	}

	let busy = new Set<number>();

	async function cancelPending(event_id: number) {
		busy = new Set([...busy, event_id]);
		await fetch(`/api/ledger/${event_id}`, { method: 'DELETE' });
		busy = new Set([...busy].filter((id) => id !== event_id));
		await invalidateAll();
	}

	async function undoApplied(event_id: number) {
		busy = new Set([...busy, event_id]);
		await fetch('/api/ledger', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ kind: 'revoke', target_event_id: event_id })
		});
		busy = new Set([...busy].filter((id) => id !== event_id));
		await invalidateAll();
	}

	async function cancelRevoke(revokeEventId: number) {
		busy = new Set([...busy, revokeEventId]);
		await fetch(`/api/ledger/${revokeEventId}`, { method: 'DELETE' });
		busy = new Set([...busy].filter((id) => id !== revokeEventId));
		await invalidateAll();
	}

	function revokeIdFor(target_id: number): number | undefined {
		return events.find(
			(e) =>
				e.kind === 'revoke' &&
				e.revoked_at === null &&
				e.payload.kind === 'revoke' &&
				e.payload.target_event_id === target_id
		)?.event_id;
	}
</script>

{#if events.length > 0}
	<div class="ledger-panel">
		<h3>Your Profile Changes</h3>

		{#if appliedEvents.length > 0}
			<div class="item-list">
				<h4>Applied ({appliedEvents.length})</h4>
				{#each appliedEvents as e (e.event_id)}
					{@const revokeId = revokeIdFor(e.event_id)}
					<div class="item-row">
						<span>{describeEvent(e)}</span>
						<div class="row-actions">
							{#if revokeId !== undefined}
								<span class="status">undo pending</span>
								<button
									class="btn-sm"
									disabled={busy.has(revokeId)}
									on:click={() => cancelRevoke(revokeId)}>Cancel undo</button
								>
							{:else}
								<button
									class="btn-sm"
									disabled={busy.has(e.event_id)}
									on:click={() => undoApplied(e.event_id)}>Undo</button
								>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		{/if}

		{#if pendingEvents.length > 0}
			<div class="item-list">
				<h4>Pending — next data refresh ({pendingEvents.length})</h4>
				{#each pendingEvents as e (e.event_id)}
					{@const skipped = skippedReasons.get(e.event_id)}
					<div class="item-row">
						<div>
							<span>{describeEvent(e)}</span>
							{#if skipped}
								<span class="hint-text"> · skipped: {skipped}</span>
							{:else if e.moderation === 'pending_review'}
								<span class="hint-text"> · awaiting review</span>
							{/if}
						</div>
						<div class="row-actions">
							{#if e.kind !== 'revoke'}
								<button
									class="btn-sm destructive"
									disabled={busy.has(e.event_id)}
									on:click={() => cancelPending(e.event_id)}>×</button
								>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</div>
{/if}

<style>
	.ledger-panel {
		margin-top: 24px;
		padding: 14px 16px;
		border-radius: 4px;
		border: 1px solid rgba(var(--color-range-15), 0.18);
		background: rgba(var(--color-range-15), 0.03);
		display: flex;
		flex-direction: column;
		gap: 12px;
	}

	.ledger-panel h3 {
		font-size: var(--text-base);
		margin: 0;
		opacity: 0.7;
	}

	.item-list h4 {
		font-size: var(--text-sm);
		opacity: 0.5;
		margin: 0 0 4px 0;
	}

	.item-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
		font-size: var(--text-sm);
		padding: 3px 0;
		border-bottom: 1px solid rgba(var(--color-range-15), 0.06);
	}

	.row-actions {
		display: flex;
		align-items: center;
		gap: 6px;
		flex-shrink: 0;
	}
</style>
