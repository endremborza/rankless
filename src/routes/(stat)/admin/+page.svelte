<script lang="ts">
	import { base } from '$app/paths';
	import type { PageData } from './$types';

	export let data: PageData;

	$: users = data.users;
	$: emailCount = users.filter((u) => u.consent).length;
</script>

<svelte:head><title>Admin · Rankless</title></svelte:head>

<div class="admin">
	<h1>Admin</h1>
	<p class="nav">
		<a href="{base}/admin/ledger">→ Ledger review queue ({data.pendingCount} pending)</a> ·
		<a href="{base}/mcp">→ MCP exploration sessions</a>
	</p>

	<h1 class="section">Users &amp; email consent</h1>
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
</div>

<style>
	.admin {
		max-width: 1100px;
		margin: 1rem auto;
		padding: 0 1rem;
	}
	h1.section {
		margin-top: 2rem;
	}
	.nav {
		font-size: 0.95rem;
	}
	.sub {
		color: #666;
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
</style>
