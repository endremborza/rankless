<script lang="ts">
	import { base } from '$app/paths';
	import type { PageData } from './$types';

	export let data: PageData;
</script>

<svelte:head><title>Games admin · Rankless</title></svelte:head>

<div class="admin">
	<nav class="topnav"><a href="{base}/admin">← Admin</a></nav>

	<h1>Games</h1>
	<p class="sub">
		Card packs come from the MCP object store; "served" is the pack after the serve-time gates
		(latest non-rejected version, and for Place the Name at least one top-percentile badge). Runs
		are logged daily + practice rounds.
	</p>

	<div class="table-wrap">
		<table>
			<thead>
				<tr>
					<th>game</th>
					<th>cards served</th>
					<th>cards current</th>
					<th>runs logged</th>
					<th>cards</th>
				</tr>
			</thead>
			<tbody>
				{#each data.games as g (g.route)}
					<tr>
						<td><a href="{base}{g.route}">{g.title}</a></td>
						<td>{g.packServed}</td>
						<td>{g.packCurrent}</td>
						<td>{g.runs}</td>
						<td><a href="{base}{g.review}">→ review</a></td>
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
