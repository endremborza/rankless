<script lang="ts">
	import type { AppliedManifest } from '$lib/wire/rankless_rs/user_ledger';
	import type { PaperOut } from '$lib/wire/rankless_server/responses';
	import type { LedgerEvent } from '$lib/types/ledger';
	import {
		draftOf,
		emptyDraft,
		type ComposeKind,
		type EventBody,
		type LedgerClient,
		type WriteOutcome
	} from '$lib/utils/ledger-client';
	import {
		ACTION_LABELS,
		COMPOSE_COPY,
		PANEL_SECTIONS,
		REPLACE_COPY,
		panelRows,
		paperMapOf,
		type PanelRow,
		type RowAction
	} from '$lib/utils/ledger-display';
	import LedgerComposeForm from './LedgerComposeForm.svelte';

	export let events: LedgerEvent[];
	export let manifest: AppliedManifest;
	export let papers: PaperOut[];
	export let semanticId: string;
	export let ledger: LedgerClient;

	const COMPOSE_KINDS = Object.keys(COMPOSE_COPY) as ComposeKind[];

	$: rows = panelRows(events, manifest, paperMapOf(papers));
	$: sections = [
		{ title: PANEL_SECTIONS.applied, applied: true, rows: rows.applied },
		{ title: PANEL_SECTIONS.pending, applied: false, rows: rows.pending }
	].filter((s) => s.rows.length > 0);

	let busy = new Set<number>();
	let editing: number | null = null;

	async function whileBusy(event_id: number, write: () => Promise<WriteOutcome>) {
		busy = new Set([...busy, event_id]);
		const outcome = await write();
		busy = new Set([...busy].filter((id) => id !== event_id));
		return outcome;
	}

	function act(action: RowAction, row: PanelRow) {
		const { event_id } = row.event;
		switch (action) {
			case 'undo':
				return whileBusy(event_id, () => ledger.undo(event_id));
			case 'cancel_undo':
				return whileBusy(event_id, () => ledger.withdraw(row.undoEventId!));
			case 'withdraw':
				return whileBusy(event_id, () => ledger.withdraw(event_id));
			case 'change':
			case 'edit':
				editing = editing === event_id ? null : event_id;
		}
	}

	async function replace(row: PanelRow, applied: boolean, body: EventBody) {
		const { event } = row;
		const outcome = await whileBusy(event.event_id, () => ledger.replace(event, applied, body));
		if (outcome === 'done') editing = null;
		return outcome;
	}
</script>

<div class="ledger-panel">
	{#each COMPOSE_KINDS as kind (kind)}
		{@const copy = COMPOSE_COPY[kind]}
		<div class="tool-section">
			<h3>{copy.title}</h3>
			{#if copy.hint}<p class="hint-text">{copy.hint}</p>{/if}
			<LedgerComposeForm
				draft={emptyDraft(kind)}
				ownSemanticId={semanticId}
				submitLabel={copy.submitLabel}
				doneText={copy.doneText}
				submit={ledger.post}
			/>
		</div>
	{/each}

	{#if sections.length > 0}
		<div class="tool-section">
			<h3>Your Profile Changes</h3>
			{#each sections as section (section.title)}
				<div class="item-list">
					<h4>{section.title} ({section.rows.length})</h4>
					{#each section.rows as row (row.event.event_id)}
						{@const draft = editing === row.event.event_id ? draftOf(row.event.payload) : null}
						<div class="item-row">
							<div>
								<span>{row.text}</span>
								{#each [row.note, row.status] as detail, i (i)}
									{#if detail}<span class="hint-text"> · {detail}</span>{/if}
								{/each}
							</div>
							<div class="row-actions">
								{#each row.actions as action (action)}
									<button
										class="btn-sm"
										class:destructive={action === 'withdraw'}
										aria-label={action === 'withdraw' ? 'Withdraw' : undefined}
										disabled={busy.has(row.event.event_id)}
										on:click={() => act(action, row)}>{ACTION_LABELS[action]}</button
									>
								{/each}
							</div>
						</div>
						{#if draft}
							<div class="row-form">
								<LedgerComposeForm
									{draft}
									ownSemanticId={semanticId}
									submitLabel={REPLACE_COPY.submitLabel}
									doneText={REPLACE_COPY.doneText}
									submit={(body) => replace(row, section.applied, body)}
									cancel={() => (editing = null)}
								/>
							</div>
						{/if}
					{/each}
				</div>
			{/each}
		</div>
	{/if}
</div>

<style>
	.ledger-panel {
		margin-bottom: 20px;
		padding: 14px 16px;
		border-radius: 4px;
		border: 1px solid rgba(var(--color-range-15), 0.18);
		background: rgba(var(--color-range-15), 0.04);
		display: flex;
		flex-direction: column;
		gap: 20px;
	}

	.tool-section {
		display: flex;
		flex-direction: column;
		gap: 6px;
	}

	.tool-section h3 {
		font-size: var(--text-base);
		margin: 0;
		text-align: left;
	}

	.item-list h4 {
		font-size: var(--text-sm);
		opacity: 0.5;
		margin: 0 0 4px 0;
	}

	.item-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 8px;
		font-size: var(--text-sm);
		padding: 3px 0;
		border-bottom: 1px solid rgba(var(--color-range-15), 0.06);
	}

	.row-actions {
		display: flex;
		align-items: center;
		gap: 6px;
		flex-shrink: 0;
	}

	.row-form {
		padding: 6px 0 8px;
	}
</style>
