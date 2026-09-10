<script lang="ts">
	import { base } from '$app/paths';
	import type { PageData } from './$types';
	import { BRAND, PATH } from '$lib/utils/game-geo';

	export let data: PageData;
</script>

<svelte:head><title>Games admin · Rankless</title></svelte:head>

<div class="admin">
	<nav class="topnav"><a href="{base}/admin">← Admin</a></nav>

	<h1>Games</h1>
	<p class="sub">
		<a href="{base}{PATH}">{BRAND}</a> serves one pack per card kind from the MCP object store;
		"served" is the pack after the serve-time gates (latest non-rejected version, and for country
		cards at least one top-percentile badge). A daily admits only a few medical names, so that share
		is shown.
		{data.runs} runs logged (daily + survival).
		<a href="{base}/admin/games/cards">→ review the cards</a>
	</p>

	<div class="table-wrap">
		<table>
			<thead>
				<tr>
					<th>kind</th>
					<th>cards served</th>
					<th>cards current</th>
					<th>medical-named</th>
				</tr>
			</thead>
			<tbody>
				{#each data.kinds as k (k.kind)}
					<tr>
						<td>{k.kind}</td>
						<td>{k.served}</td>
						<td>{k.current}</td>
						<td>{k.medical}</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</div>

<style>
	.admin {
		max-width: 800px;
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
	}

	th {
		color: var(--color-text-light);
		font-weight: 600;
	}
</style>
