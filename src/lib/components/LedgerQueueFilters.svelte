<script lang="ts">
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';

	export let state: string;
	export let kind: string;
	export let actor: string;
	export let page: number;
	export let per: number;
	export let total: number;
	export let actors: { orcid: string; pending: number }[];

	const STATES = ['pending', 'accepted', 'rejected', 'auto_ok', 'all'];
	const KINDS = [
		'all',
		'claim_paper',
		'disown_paper',
		'merge_papers',
		'merge_authors',
		'revoke',
		'add_paper_request'
	];
	const PER_CHOICES = [25, 50, 100, 200];

	$: pages = Math.max(1, Math.ceil(total / per));
	$: from = total === 0 ? 0 : (page - 1) * per + 1;
	$: to = Math.min(page * per, total);

	$: navigate = (patch: Record<string, string | number>) => {
		const params = new URLSearchParams({
			state,
			kind,
			actor,
			page: String(page),
			per: String(per)
		});
		for (const [k, v] of Object.entries(patch)) params.set(k, String(v));
		if (!('page' in patch)) params.set('page', '1');
		if (params.get('actor') === '') params.delete('actor');
		goto(`${base}/admin/ledger?${params}`, { keepFocus: true, noScroll: true });
	};
</script>

<div class="filters">
	<label>
		state
		<select value={state} on:change={(e) => navigate({ state: e.currentTarget.value })}>
			{#each STATES as s, i (i)}<option value={s}>{s}</option>{/each}
		</select>
	</label>
	<label>
		kind
		<select value={kind} on:change={(e) => navigate({ kind: e.currentTarget.value })}>
			{#each KINDS as k, i (i)}<option value={k}>{k}</option>{/each}
		</select>
	</label>
	<label>
		claimant
		<select value={actor} on:change={(e) => navigate({ actor: e.currentTarget.value })}>
			<option value="">all</option>
			{#each actors as a, i (i)}
				<option value={a.orcid}>{a.orcid} ({a.pending} pending)</option>
			{/each}
		</select>
	</label>
	<label>
		per page
		<select value={String(per)} on:change={(e) => navigate({ per: e.currentTarget.value })}>
			{#each PER_CHOICES as p, i (i)}<option value={String(p)}>{p}</option>{/each}
		</select>
	</label>
	<span class="pager">
		<button disabled={page <= 1} on:click={() => navigate({ page: page - 1 })}>‹</button>
		{from}–{to} of {total}
		<button disabled={page >= pages} on:click={() => navigate({ page: page + 1 })}>›</button>
	</span>
</div>

<style>
	.filters {
		display: flex;
		gap: 1rem;
		align-items: center;
		flex-wrap: wrap;
		margin: 0.8rem 0;
		font-size: 0.85rem;
	}
	label {
		display: inline-flex;
		gap: 0.35rem;
		align-items: center;
		color: #444;
	}
	.pager {
		margin-left: auto;
		display: inline-flex;
		gap: 0.5rem;
		align-items: center;
		white-space: nowrap;
	}
	button {
		cursor: pointer;
	}
	button:disabled {
		cursor: default;
		opacity: 0.5;
	}
</style>
