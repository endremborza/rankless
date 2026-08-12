<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import { base } from '$app/paths';
	import LedgerClaimantGroup from '$lib/components/LedgerClaimantGroup.svelte';
	import LedgerQueueFilters from '$lib/components/LedgerQueueFilters.svelte';
	import type { AdminReviewRow } from '$lib/types/review';
	import type { PageData } from './$types';

	export let data: PageData;

	// Moderation responses patch rows locally (no full reload); patches are cleared
	// whenever the loader genuinely reruns with fresh rows (enrichment, navigation).
	let patches = new Map<number, Partial<AdminReviewRow>>();
	$: rows = (data.rows as AdminReviewRow[]).map((r) => {
		const patch = patches.get(r.event_id);
		return patch ? { ...r, ...patch } : r;
	});

	let selected = new Set<number>();
	let busy = new Set<number>();
	let lastError = '';
	let enriching = false;
	let enrichNote = '';

	type Group = { orcid: string; rows: AdminReviewRow[] };
	function groupByActor(rs: AdminReviewRow[]): Group[] {
		const groups: Group[] = [];
		for (const row of rs) {
			const last = groups[groups.length - 1];
			if (last && last.orcid === row.orcid) last.rows.push(row);
			else groups.push({ orcid: row.orcid, rows: [row] });
		}
		return groups;
	}
	$: groups = groupByActor(rows);

	function toggle(id: number) {
		const s = new Set(selected);
		if (s.has(id)) s.delete(id);
		else s.add(id);
		selected = s;
	}

	function toggleGroup(event_ids: number[], on: boolean) {
		const s = new Set(selected);
		for (const id of event_ids) {
			if (on) s.add(id);
			else s.delete(id);
		}
		selected = s;
	}

	async function moderate(event_ids: number[], decision: 'accepted' | 'rejected') {
		busy = new Set([...busy, ...event_ids]);
		lastError = '';
		try {
			const res = await fetch('/api/admin/moderate', {
				method: 'POST',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify({ event_ids, decision })
			});
			if (!res.ok) {
				lastError = `Failed to ${decision} ${event_ids.length} event(s) (${res.status})`;
				return;
			}
			const { updated } = (await res.json()) as { updated: number[] };
			const updatedSet = new Set(updated);
			const stamp = new Date().toISOString().slice(0, 19).replace('T', ' ');
			const next = new Map(patches);
			for (const id of updated) {
				next.set(id, {
					moderation: decision,
					moderated_by: data.me,
					moderated_at: stamp,
					auto_moderated: false,
					pipeline:
						decision === 'accepted'
							? { label: 'awaiting rebuild', cls: 'awaiting' }
							: { label: '—', cls: 'muted' }
				});
			}
			patches = next;
			selected = new Set([...selected].filter((id) => !updatedSet.has(id)));
		} finally {
			const b = new Set(busy);
			for (const id of event_ids) b.delete(id);
			busy = b;
		}
	}

	async function fetchMetadata() {
		enriching = true;
		lastError = '';
		let fetched = 0;
		let autoAccepted = 0;
		try {
			for (;;) {
				const res = await fetch('/api/admin/enrich', {
					method: 'POST',
					headers: { 'content-type': 'application/json' },
					body: JSON.stringify({})
				});
				if (!res.ok) {
					lastError = `Metadata fetch failed (${res.status})`;
					return;
				}
				const report = (await res.json()) as {
					fetched: number;
					remaining: number;
					autoAccepted: number[];
					errors: { source: string; key: string }[];
				};
				fetched += report.fetched;
				autoAccepted += report.autoAccepted.length;
				enrichNote = `fetched ${fetched}, ${report.remaining} remaining…`;
				if (report.errors.length > 0) {
					lastError = `${report.errors.length} fetch error(s), e.g. ${report.errors[0].source}:${report.errors[0].key}`;
				}
				if (report.remaining === 0) break;
			}
			enrichNote = `fetched ${fetched}${autoAccepted ? ` · auto-accepted ${autoAccepted} proven claim(s)` : ''}`;
			patches = new Map();
			await invalidateAll();
		} finally {
			enriching = false;
		}
	}
</script>

<svelte:head><title>Ledger review · Rankless</title></svelte:head>

<div class="queue">
	<h1>Ledger review</h1>
	<p class="nav"><a href="{base}/admin">← Admin</a> · <a href="{base}/mcp">MCP sessions</a></p>
	<p class="sub">
		Approving a change marks it accepted; it is applied on the next data rebuild, not immediately.
		“implemented” means the change is live in the current data{data.currentRunId
			? ` (run ${data.currentRunId})`
			: ''}. Claims proven by a Crossref/OpenAlex authorship record are accepted automatically; AI
		verdicts on the rest are advisory.
	</p>

	<div class="tools">
		<button disabled={enriching || data.missingEnrichment === 0} on:click={fetchMetadata}>
			{enriching ? 'Fetching…' : `Fetch metadata (${data.missingEnrichment} missing)`}
		</button>
		{#if enrichNote}<span class="note">{enrichNote}</span>{/if}
	</div>

	<LedgerQueueFilters
		state={data.params.state}
		kind={data.params.kind}
		actor={data.params.actor}
		page={data.params.page}
		per={data.params.per}
		total={data.total}
		actors={data.pendingActors}
	/>

	{#if lastError}<p class="err">{lastError}</p>{/if}

	{#if selected.size > 0}
		<div class="bulk">
			<span>{selected.size} selected</span>
			<button class="ok" on:click={() => moderate([...selected], 'accepted')}
				>Approve selected</button
			>
			<button class="no" on:click={() => moderate([...selected], 'rejected')}
				>Reject selected</button
			>
		</div>
	{/if}

	{#each groups as group, i (i)}
		<LedgerClaimantGroup
			rows={group.rows}
			{selected}
			{busy}
			on:toggle={(e) => toggle(e.detail)}
			on:toggleGroup={(e) => toggleGroup(e.detail.event_ids, e.detail.on)}
			on:moderate={(e) => moderate(e.detail.event_ids, e.detail.decision)}
		/>
	{:else}
		<p class="muted">No events match the current filters.</p>
	{/each}
</div>

<style>
	.queue {
		max-width: 1200px;
		margin: 1rem auto;
		padding: 0 1rem;
	}
	.sub {
		color: #666;
		font-size: 0.9rem;
	}
	.nav {
		font-size: 0.9rem;
	}
	.tools {
		display: flex;
		gap: 0.8rem;
		align-items: center;
	}
	.note {
		color: #666;
		font-size: 0.85rem;
	}
	.err {
		color: #b00020;
		font-size: 0.9rem;
	}
	.muted {
		color: #999;
	}
	.bulk {
		position: sticky;
		top: 0;
		background: #f6f8fa;
		border: 1px solid #e0e4e8;
		border-radius: 6px;
		padding: 0.5rem 0.8rem;
		margin-bottom: 0.8rem;
		display: flex;
		gap: 0.8rem;
		align-items: center;
		z-index: 2;
	}
	button {
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
