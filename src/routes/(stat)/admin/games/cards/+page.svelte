<script lang="ts">
	import { base } from '$app/paths';
	import { entToLink } from '$lib/tree-functions';
	import type { PageData } from './$types';
	import { ccFlag, ccName } from '$lib/utils/game';
	import { BRAND } from '$lib/utils/game-countries';

	export let data: PageData;

	$: cards = data.cards;
	$: servedCount = cards.filter((c) => c.served).length;

	// A rejection must carry a reason (stored, reviewable later), collected via
	// prompt like the /mcp review list does.
	function confirmStatus(e: SubmitEvent, target: string) {
		if (target !== 'rejected') return;
		const note = prompt('Why reject? (kept for later review)');
		if (!note?.trim()) {
			e.preventDefault();
			return;
		}
		const form = e.currentTarget as HTMLFormElement;
		(form.elements.namedItem('note') as HTMLInputElement).value = note.trim();
	}
</script>

<svelte:head><title>{BRAND} cards · Rankless</title></svelte:head>

<div class="admin">
	<nav class="topnav"><a href="{base}/admin/games">← Games</a></nav>

	<h1>{BRAND} — cards</h1>
	<p class="sub">
		{cards.length} cards, {servedCount} served. Every card at its latest version: the name players see,
		the true country, the decoy options, the reveal text, and the badge standings. A wrong or misleading
		card gets rejected here (with a reason); rejecting frees its institution for re-mining.
	</p>

	<div class="table-wrap">
		<table>
			<thead>
				<tr>
					<th>status</th>
					<th>name</th>
					<th>answer</th>
					<th>decoys</th>
					<th>badges</th>
					<th>reveal text</th>
					<th>actions</th>
				</tr>
			</thead>
			<tbody>
				{#each cards as c (c.id)}
					<tr class:rejected={c.status === 'rejected'}>
						<td class="status-cell">
							<span class="status st-{c.status}">{c.status}</span>
							{#if c.served}<span class="served" title="in the served pack">●</span>{/if}
							{#if c.statusNote}<div class="note-line">{c.statusNote}</div>{/if}
						</td>
						<td>
							{#if c.card}
								<a href={entToLink({ rootType: 'institutions', semanticId: c.semId })}
									>{c.card.name}</a
								>
							{:else}
								<span class="muted">payload missing on this box</span>
							{/if}
							<div class="mono sem">{c.semId}</div>
						</td>
						{#if c.card}
							<td class="nowrap">{ccFlag(c.card.cc)} {ccName(c.card.cc)}</td>
							<td>
								{#each c.card.decoys as d, i (i)}
									<span class="nowrap">{ccFlag(d)} {ccName(d)}</span>{i < 2 ? ', ' : ''}
								{/each}
							</td>
							<td>
								{#each c.badges as b, i (i)}
									<div class="nowrap">{b.label} · {b.subfield}</div>
								{:else}
									<span class="muted">none</span>
								{/each}
							</td>
							<td class="reveal">{c.card.note}</td>
						{:else}
							<td colspan="4" class="muted">—</td>
						{/if}
						<td class="actions">
							{#each ['approved', 'rejected'] as target (target)}
								{#if c.status !== target}
									<form method="POST" action="?/review" on:submit={(e) => confirmStatus(e, target)}>
										<input type="hidden" name="id" value={c.id} />
										<input type="hidden" name="status" value={target} />
										<input type="hidden" name="note" value="" />
										<button type="submit" class="link" class:danger={target === 'rejected'}>
											{target === 'approved' ? 'approve' : 'reject'}
										</button>
									</form>
								{/if}
							{/each}
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</div>

<style>
	.admin {
		max-width: 1300px;
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
		font-size: var(--text-sm);
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

	tr.rejected td {
		opacity: 0.55;
	}

	.status-cell {
		white-space: nowrap;
	}

	.status.st-approved {
		color: var(--color-ok);
	}

	.status.st-rejected {
		color: var(--color-err);
	}

	.served {
		color: var(--color-ok);
		margin-left: 0.3rem;
	}

	.note-line {
		max-width: 12rem;
		white-space: normal;
		color: var(--color-text-light);
		font-size: var(--text-xs);
	}

	.mono.sem {
		font-family: var(--font-mono);
		font-size: var(--text-xs);
		color: var(--color-text-light);
	}

	.nowrap {
		white-space: nowrap;
	}

	.reveal {
		min-width: 22rem;
	}

	.muted {
		color: var(--color-text-light);
	}

	.actions form {
		display: inline;
	}

	.actions .link {
		background: none;
		border: none;
		padding: 0;
		margin-right: 0.5rem;
		color: var(--accent-text);
		cursor: pointer;
		font: inherit;
		text-decoration: underline;
	}

	.actions .link.danger {
		color: var(--color-err);
	}
</style>
