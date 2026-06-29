<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import type { LedgerPayload } from '$lib/types/ledger';
	import type { PageData } from './$types';

	export let data: PageData;

	$: events = data.events;
	$: pendingCount = events.filter((e) => e.moderation === 'pending_review').length;

	let busy = new Set<number>();
	let lastError = '';

	// All values below come from OpenAlex display snapshots (untrusted) — they are rendered via
	// plain `{}` interpolation only (Svelte auto-escapes). Do NOT switch any of this to {@html}.
	function summarize(p: LedgerPayload): string {
		switch (p.kind) {
			case 'disown_paper':
				return `disown “${p.work.display_snapshot.title || p.work.doi || p.work.oa_id || '?'}”`;
			case 'claim_paper':
				return `claim “${p.work.display_snapshot.title || p.work.doi || p.work.oa_id || '?'}”`;
			case 'merge_papers':
				return `keep “${p.keep.display_snapshot.title}” ⇐ drop “${p.drop.display_snapshot.title}”`;
			case 'merge_authors':
				return `keep “${p.keep.display_snapshot.display_name}” ⇐ drop “${p.drop.display_snapshot.display_name}”${p.note ? ` — note: ${p.note}` : ''}`;
			case 'revoke':
				return `revoke event #${p.target_event_id}${p.reason ? ` — ${p.reason}` : ''}`;
			case 'moderation_decision':
				return `${p.decision} event #${p.target_event_id}`;
			case 'add_paper_request':
				return 'add-paper request';
		}
	}

	async function moderate(eventId: number, decision: 'accepted' | 'rejected') {
		busy = new Set(busy).add(eventId);
		lastError = '';
		try {
			const res = await fetch('/api/admin/moderate', {
				method: 'POST',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify({ event_id: eventId, decision })
			});
			if (res.ok) await invalidateAll();
			else lastError = `Failed to ${decision} event #${eventId} (${res.status})`;
		} finally {
			const b = new Set(busy);
			b.delete(eventId);
			busy = b;
		}
	}
</script>

<svelte:head><title>Admin · ledger moderation</title></svelte:head>

<div class="admin">
	<h1>Ledger moderation</h1>
	<p class="sub">
		{events.length} most recent events · {pendingCount} pending review. Approving a change marks it accepted;
		it is applied on the next data rebuild, not immediately.
	</p>
	{#if lastError}<p class="err">{lastError}</p>{/if}

	<table>
		<thead>
			<tr>
				<th>#</th>
				<th>actor</th>
				<th>kind</th>
				<th>summary</th>
				<th>created</th>
				<th>status</th>
				<th></th>
			</tr>
		</thead>
		<tbody>
			{#each events as e, i (i)}
				<tr class:pending={e.moderation === 'pending_review'} class:revoked={e.revoked_at !== null}>
					<td>{e.event_id}</td>
					<td class="mono">{e.orcid}</td>
					<td>{e.kind}</td>
					<td>{summarize(e.payload)}</td>
					<td class="mono">{e.created_at}</td>
					<td>
						{e.moderation}{e.moderated_by ? ` · by ${e.moderated_by}` : ''}{e.revoked_at
							? ' · revoked'
							: ''}
					</td>
					<td class="actions">
						{#if e.moderation === 'pending_review' && e.revoked_at === null}
							<button
								class="ok"
								disabled={busy.has(e.event_id)}
								on:click={() => moderate(e.event_id, 'accepted')}>Approve</button
							>
							<button
								class="no"
								disabled={busy.has(e.event_id)}
								on:click={() => moderate(e.event_id, 'rejected')}>Reject</button
							>
						{/if}
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>

<style>
	.admin {
		max-width: 1100px;
		margin: 1rem auto;
		padding: 0 1rem;
	}
	.sub {
		color: #666;
		font-size: 0.9rem;
	}
	.err {
		color: #b00020;
		font-size: 0.9rem;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.85rem;
	}
	th,
	td {
		text-align: left;
		padding: 0.4rem 0.5rem;
		border-bottom: 1px solid #eee;
		vertical-align: top;
	}
	.mono {
		font-family: monospace;
		font-size: 0.8rem;
		white-space: nowrap;
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
