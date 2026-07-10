<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import type { LedgerPayload } from '$lib/types/ledger';
	import type { PageData } from './$types';

	export let data: PageData;

	type EventRow = PageData['events'][number];

	$: events = data.events;
	$: users = data.users;
	$: pendingCount = events.filter((e) => e.moderation === 'pending_review').length;
	$: appliedSet = new Set(data.applied);
	$: skippedMap = new Map(data.skipped.map((s) => [s.event_id, s.reason]));
	$: emailCount = users.filter((u) => u.consent).length;

	let onlyImplemented = false;
	$: shownEvents = onlyImplemented ? events.filter((e) => appliedSet.has(e.event_id)) : events;

	let busy = new Set<number>();
	let lastError = '';

	// Whether (and how) a requested change has reached the live data. `appliedSet` unions
	// every pipeline run's applied ids, so this answers "is this change implemented yet?".
	$: pipelineStatus = (e: EventRow): { label: string; cls: string } => {
		if (appliedSet.has(e.event_id)) return { label: 'implemented', cls: 'applied' };
		const reason = skippedMap.get(e.event_id);
		if (reason) return { label: `skipped · ${reason}`, cls: 'skipped' };
		if (e.revoked_at || e.moderation === 'rejected') return { label: '—', cls: 'muted' };
		if (e.moderation === 'pending_review') return { label: 'awaiting review', cls: 'muted' };
		return { label: 'awaiting rebuild', cls: 'awaiting' };
	};

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

<svelte:head><title>Admin · Rankless</title></svelte:head>

<div class="admin">
	<h1>Users &amp; email consent</h1>
	<p class="sub">
		{users.length} signed-in {users.length === 1 ? 'user' : 'users'} · {emailCount} with an active email
		consent. Emails are collected only with explicit, per-purpose consent and can be withdrawn by the
		user at any time.
	</p>

	<table>
		<thead>
			<tr>
				<th>actor</th>
				<th>name</th>
				<th>logins</th>
				<th>last login</th>
				<th>email</th>
				<th>consented to</th>
				<th>granted</th>
			</tr>
		</thead>
		<tbody>
			{#each users as u, i (i)}
				<tr>
					<td class="mono">{u.orcid}</td>
					<td>{u.name ?? '—'}</td>
					<td>{u.login_count || '—'}</td>
					<td class="mono">{u.last_login_at}</td>
					{#if u.consent}
						<td>{u.consent.email}</td>
						<td>{u.consent.purposes.join(', ')}</td>
						<td class="mono">{u.consent.granted_at}</td>
					{:else}
						<td colspan="3" class="muted">no email consent</td>
					{/if}
				</tr>
			{/each}
		</tbody>
	</table>

	<h1 class="section">Ledger moderation</h1>
	<p class="sub">
		{events.length} most recent events · {pendingCount} pending review. Approving a change marks it accepted;
		it is applied on the next data rebuild, not immediately. “implemented” means the change is live in
		the current data{data.currentRunId ? ` (run ${data.currentRunId})` : ''}.
	</p>
	<label class="filter">
		<input type="checkbox" bind:checked={onlyImplemented} /> show only changes implemented in the pipeline
	</label>
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
				<th>pipeline</th>
				<th></th>
			</tr>
		</thead>
		<tbody>
			{#each shownEvents as e, i (i)}
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
					<td class={pipelineStatus(e).cls}>{pipelineStatus(e).label}</td>
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
	h1.section {
		margin-top: 2.5rem;
	}
	.sub {
		color: #666;
		font-size: 0.9rem;
	}
	.filter {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.85rem;
		color: #444;
		margin-bottom: 0.6rem;
		cursor: pointer;
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
	.muted {
		color: #999;
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
