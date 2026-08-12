<script lang="ts">
	import { base } from '$app/paths';
	import { entToLink } from '$lib/tree-functions';
	import type { PageData } from './$types';

	export let data: PageData;

	$: users = data.users;
	$: names = data.names;
	$: emailCount = users.filter((u) => u.consent).length;
	$: onlineCount = users.filter((u) => u.online).length;
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
	<nav class="topnav">
		<a href="{base}/mcp">→ MCP exploration sessions</a> ·
		<a href="{base}/admin/ledger">→ Ledger review queue ({data.pendingCount} pending)</a>
	</nav>

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
</div>

<style>
	.admin {
		max-width: 1100px;
		margin: 1rem auto;
		padding: 0 1rem;
	}
	.topnav {
		margin-bottom: 1rem;
		font-size: var(--text-sm);
	}
	.sub {
		color: var(--color-text-light);
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
</style>
