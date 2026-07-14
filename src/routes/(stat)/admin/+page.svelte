<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import { entToLink } from '$lib/tree-functions';
	import type { LedgerPayload } from '$lib/types/ledger';
	import type { PageData } from './$types';

	export let data: PageData;

	type EventRow = PageData['events'][number];

	$: events = data.events;
	$: users = data.users;
	$: names = data.names;
	$: pendingCount = events.filter((e) => e.moderation === 'pending_review').length;
	// Everything the pipeline reports is keyed by an event's logical key (merge-stable), not
	// its event_id — see docs/ledger identity note. `appliedSet` unions every stored run.
	$: appliedSet = new Set(data.applied);
	$: skippedMap = new Map(data.skipped.map((s) => [s.key, s.reason]));
	// Targets an active revoke undoes; their change is dropped from the build.
	$: revertedKeys = new Set(
		events.flatMap((e) =>
			e.kind === 'revoke' && e.revoked_at === null && e.payload.kind === 'revoke'
				? [e.payload.target_key]
				: []
		)
	);
	$: emailCount = users.filter((u) => u.consent).length;
	$: onlineCount = users.filter((u) => u.online).length;

	let onlyImplemented = false;
	$: shownEvents = onlyImplemented ? events.filter((e) => appliedSet.has(e.key)) : events;

	let busy = new Set<number>();
	let lastError = '';

	// Whether (and how) a requested change has reached the live data. Revokes and the targets
	// they neutralize are control/undo actions with no standing data footprint, so they're
	// classified before the applied/skipped lookup rather than falling to "awaiting rebuild".
	$: pipelineStatus = (e: EventRow): { label: string; cls: string } => {
		if (e.revoked_at || e.moderation === 'rejected') return { label: '—', cls: 'muted' };
		if (e.kind === 'revoke') return { label: 'revocation', cls: 'muted' };
		if (revertedKeys.has(e.key)) return { label: 'reverted', cls: 'muted' };
		if (appliedSet.has(e.key)) return { label: 'implemented', cls: 'applied' };
		const reason = skippedMap.get(e.key);
		if (reason) return { label: `skipped · ${reason}`, cls: 'skipped' };
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
			case 'revoke': {
				const target = events.find((t) => t.key === p.target_key);
				return `revoke${target ? `: ${summarize(target.payload)}` : ''}${p.reason ? ` — ${p.reason}` : ''}`;
			}
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

{#snippet actorName(name: string | null, semanticId: string | null)}
	{#if name && semanticId}
		<a href={entToLink({ rootType: 'authors', semanticId })}>{name}</a>
	{:else if name}
		{name}
	{:else}
		—
	{/if}
{/snippet}

<div class="admin">
	<nav class="topnav"><a href="/mcp">→ MCP exploration sessions</a></nav>

	<h1>Users &amp; email consent</h1>
	<p class="sub">
		{users.length}
		{users.length === 1 ? 'person has' : 'people have'} taken an action · {onlineCount} currently signed
		in · {emailCount} with an active email consent. Everyone who has ever signed in, made a change, or
		granted consent is listed. Emails are collected only with explicit, per-purpose consent and can be
		withdrawn by the user at any time.
	</p>

	<div class="table-wrap">
		<table>
			<thead>
				<tr>
					<th>actor</th>
					<th>name</th>
					<th>status</th>
					<th>logins</th>
					<th>last login</th>
					<th>ledger</th>
					<th>email</th>
					<th>consented to</th>
					<th>granted</th>
				</tr>
			</thead>
			<tbody>
				{#each users as u, i (i)}
					<tr>
						<td class="mono">{u.orcid}</td>
						<td>{@render actorName(u.name, u.semantic_id)}</td>
						<td class="status-cell">
							<span class="dot" class:online={u.online}></span>{u.online ? 'online' : 'offline'}
						</td>
						<td>{u.login_count || '—'}</td>
						<td class="mono">{u.last_login_at ?? '—'}</td>
						<td>{u.event_count || '—'}</td>
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
	</div>

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

	<div class="table-wrap">
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
					<tr
						class:pending={e.moderation === 'pending_review'}
						class:revoked={e.revoked_at !== null}
					>
						<td>{e.event_id}</td>
						<td class="actor">
							{#if names[e.orcid]?.name}
								{@const a = names[e.orcid]}
								<span class="actor-name">{@render actorName(a.name, a.semanticId)}</span>
							{/if}
							<span class="mono">{e.orcid}</span>
						</td>
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
	.topnav {
		margin-bottom: 1rem;
		font-size: var(--text-sm);
	}
	.actor {
		white-space: nowrap;
	}
	.actor-name {
		display: block;
	}
	.actor .mono {
		color: var(--color-text-light);
	}
	.sub {
		color: var(--color-text-light);
		font-size: var(--text-sm);
	}
	.filter {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		font-size: var(--text-sm);
		color: var(--color-text-light);
		margin-bottom: 0.6rem;
		cursor: pointer;
	}
	.err {
		color: var(--color-err);
		font-size: var(--text-sm);
	}
	.table-wrap {
		overflow-x: auto;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--text-base);
	}
	th,
	td {
		text-align: left;
		padding: 0.4rem 0.5rem;
		border-bottom: 1px solid rgba(var(--color-range-30), 0.15);
		vertical-align: top;
	}
	th {
		color: var(--color-text-light);
		font-weight: 600;
	}
	.mono {
		font-family: var(--font-mono);
		font-size: var(--text-sm);
		white-space: nowrap;
	}
	.muted {
		color: var(--color-text-light);
	}
	.status-cell {
		white-space: nowrap;
	}
	.dot {
		display: inline-block;
		width: 0.5rem;
		height: 0.5rem;
		border-radius: 50%;
		margin-right: 0.35rem;
		vertical-align: middle;
		background: var(--color-text-light);
		opacity: 0.5;
	}
	.dot.online {
		background: var(--color-ok);
		opacity: 1;
	}
	.applied {
		color: var(--color-ok);
		font-weight: bold;
	}
	.skipped {
		color: var(--color-warn);
	}
	.awaiting {
		color: var(--color-text-light);
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
		cursor: pointer;
		font-family: inherit;
		font-size: var(--text-xs);
		padding: 2px 8px;
		border: 1px solid rgba(var(--color-range-15), 0.25);
		background: none;
		color: var(--color-text);
	}
	button:hover:not(:disabled) {
		background: rgba(var(--color-range-15), 0.08);
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
